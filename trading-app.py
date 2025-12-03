import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import random
import time
from datetime import datetime
from collections import deque
import queue
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates#
from matplotlib.patches import Rectangle

class MarketSimulator:
    def __init__(self):
        self.symbols = ["AXION", "BLUEX", "CRYPTOX", "DYNEX", "ECHELON",
                       "FUSION", "HELIX", "INFINEX", "NEXUS", "OMEGA"]
        self.data = {}
        self.histories = {s: {} for s in self.symbols}
        self.queue = queue.Queue()

        for sym in self.symbols:
            p = round(random.uniform(120, 580), 2)
            self.data[sym] = {
                'price': p, 'bid': p*0.9991, 'ask': p*1.0009,
                'volatility': random.choice([0.004, 0.008, 0.012, 0.018, 0.022]),
                'trend': random.choice([-0.0012, -0.0005, 0, 0.0005, 0.0012]),
                'volume_pressure': 0, 'user_bid': 0, 'user_ask': 0
            }

    def get_history(self, sym, tf):
        key = f"{tf}s"
        if key not in self.histories[sym]:
            self.histories[sym][key] = deque(maxlen=600)
        return self.histories[sym][key]

    def generate_book(self, sym):
        d = self.data[sym]
        mid = d['price']
        bids = [(round(mid - i*0.05 - random.uniform(0.01,0.1), 3), random.randint(80,1200)) for i in range(1,13)]
        asks = [(round(mid + i*0.05 + random.uniform(0.01,0.1), 3), random.randint(80,1200)) for i in range(1,13)]
        if d['user_bid'] > 0: bids.append((d['bid'], d['user_bid']))
        if d['user_ask'] > 0: asks.append((d['ask'], d['user_ask']))
        return {
            'bids': sorted(bids, key=lambda x: x[0], reverse=True)[:15],
            'asks': sorted(asks, key=lambda x: x[0])[:15]
        }

    def run(self):
        while True:
            time.sleep(0.07 + random.random()*0.13)
            sym = random.choice(self.symbols)
            d = self.data[sym]

            move = d['trend'] + random.gauss(0, d['volatility']) + d['volume_pressure']*0.8
            d['volume_pressure'] *= 0.88
            new_price = max(0.01, d['price'] * (1 + move))
            old_price = d['price']
            d['price'] = round(new_price, 3)
            spread = max(0.05, abs(move)*50 + random.uniform(0.03, 0.35))
            d['bid'] = round(d['price'] - spread/2, 3)
            d['ask'] = round(d['price'] + spread/2, 3)

            now = datetime.now()
            for tf in [5,15,30,60,300]:
                bucket = now.replace(second=(now.second // tf)*tf, microsecond=0)
                hist = self.get_history(sym, tf)
                if not hist or hist[-1]['time'] != bucket:
                    if hist: hist[-1]['close'] = old_price
                    hist.append({'time': bucket, 'open': old_price, 'high': new_price,
                                'low': new_price, 'close': new_price, 'volume': random.randint(200,800)})
                else:
                    c = hist[-1]
                    c['high'] = max(c['high'], new_price)
                    c['low'] = min(c['low'], new_price)
                    c['close'] = new_price
                    c['volume'] += random.randint(50, 400)

            if random.random() < 0.92:
                side = random.choice(['buy','sell'])
                size = random.randint(200, 35000)
                price = round(d['price'] + random.uniform(-0.4, 0.4), 3)
                impact = (size / 1000.0) * 0.004 * (1 if side == 'buy' else -1)
                d['volume_pressure'] += impact
                self.queue.put(('trade', {'sym': sym, 'side': side, 'size': size,
                                        'price': price, 'time': now.strftime("%H:%M:%S.%f")[:12]}))

            self.queue.put(('tick', sym))
            self.queue.put(('dom', sym))


class TradingApp:
    LEVERAGE = 1000

    def __init__(self, root):
        self.root = root
        self.root.title("NEXUS TERMINAL • PRO")
        self.root.geometry("1920x1080")
        self.root.configure(bg="#0d1117")

        self.sim = MarketSimulator()
        self.cash = 10000.0
        self.positions = {}
        self.symbol = tk.StringVar(value="NEXUS")
        self.timeframe = tk.StringVar(value="5s")
        self.trade_markers = {sym: [] for sym in self.sim.symbols}
        self.in_margin_call = False

        self.setup_ui()
        threading.Thread(target=self.sim.run, daemon=True).start()
        self.root.after(50, self.process_queue)

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#161b22", foreground="#c9d1d9", fieldbackground="#161b22", rowheight=22)
        style.configure("Treeview.Heading", background="#21262d", foreground="#58a6ff", font=("Helvetica", 10, "bold"))
        style.map("Treeview", background=[("selected", "#238636")])
        style.map("Treeview.Heading", background=[("active", "#238636")])

        header = tk.Frame(self.root, bg="#0d1117", height=90)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="NEXUS TERMINAL • PRO", font=("Helvetica", 32, "bold"),
                fg="#58a6ff", bg="#0d1117").pack(side=tk.LEFT, padx=30, pady=15)

        right_header = tk.Frame(header, bg="#0d1117")
        right_header.pack(side=tk.RIGHT, padx=30)

        # Balance & Max Buy Power
        info_frame = tk.Frame(right_header, bg="#0d1117")
        info_frame.pack(anchor="e")

        self.balance_label = tk.Label(info_frame, text="Balance: $10,000", font=("Consolas", 14), fg="#79c0ff", bg="#0d1117")
        self.balance_label.pack(anchor="e")
        self.margin_label = tk.Label(info_frame, text="Used Margin: $0", font=("Consolas", 13), fg="#c9d1d9", bg="#0d1117")
        self.margin_label.pack(anchor="e")
        self.free_margin_label = tk.Label(info_frame, text="Free Margin: $10,000", font=("Consolas", 13), fg="#79c0ff", bg="#0d1117")
        self.free_margin_label.pack(anchor="e")
        self.max_qty_label = tk.Label(info_frame, text="Max Buy: 0 qty", font=("Consolas", 13, "bold"), fg="#ffa657", bg="#0d1117")
        self.max_qty_label.pack(anchor="e")
        self.pnl_label = tk.Label(info_frame, text="P&L: $0.00", font=("Consolas", 16, "bold"), fg="#79c0ff", bg="#0d1117")
        self.pnl_label.pack(anchor="e", pady=(5,0))

        btn_frame = tk.Frame(right_header, bg="#0d1117")
        btn_frame.pack(anchor="e", pady=10)
        tk.Button(btn_frame, text="+ $100k", command=self.add_100k, bg="#238636", fg="white",
                 font=("Helvetica", 12, "bold"), relief="flat", padx=25, pady=12, cursor="hand2").pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="Add Custom", command=self.add_funds, bg="#da3633", fg="white",
                 font=("Helvetica", 12, "bold"), relief="flat", padx=20, pady=12, cursor="hand2").pack(side=tk.LEFT)

        # Main Layout
        main = tk.Frame(self.root, bg="#0d1117")
        main.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        chart_frame = tk.LabelFrame(main, text=" Chart ", font=("Helvetica", 14, "bold"), fg="#58a6ff", bg="#161b22", bd=2, relief="flat")
        chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,10))

        toolbar = tk.Frame(chart_frame, bg="#161b22")
        toolbar.pack(fill=tk.X, pady=10, padx=20)
        tk.Label(toolbar, text="Symbol:", fg="#c9d1d9", bg="#161b22").pack(side=tk.LEFT)
        ttk.Combobox(toolbar, textvariable=self.symbol, values=self.sim.symbols, state="readonly", width=12).pack(side=tk.LEFT, padx=10)
        tk.Label(toolbar, text="TF:", fg="#c9d1d9", bg="#161b22").pack(side=tk.LEFT, padx=(30,5))
        ttk.Combobox(toolbar, textvariable=self.timeframe, values=["5s","15s","30s","1m","5m"], state="readonly", width=8).pack(side=tk.LEFT)

        self.fig = Figure(figsize=(14, 10), facecolor="#0d1117")
        self.ax = self.fig.add_subplot(111, facecolor="#0d1117")
        self.ax.tick_params(axis='both', colors='white')  # White axis text
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Right Panel
        right = tk.Frame(main, bg="#161b22", width=520)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10,0))
        right.pack_propagate(False)

        # Order Entry
        order = tk.LabelFrame(right, text=" Order Entry ", font=("Helvetica", 13, "bold"), fg="#58a6ff", bg="#161b22")
        order.pack(fill=tk.X, pady=(0,15), padx=20)

        tk.Label(order, text="Quantity:", fg="#c9d1d9", bg="#161b22").grid(row=0, column=0, sticky="w", padx=20, pady=12)
        self.qty = tk.StringVar(value="5000")
        tk.Entry(order, textvariable=self.qty, font=("Consolas", 14), width=12, bg="#0d1117", fg="white", insertbackground="white").grid(row=0, column=1, padx=20, pady=12)

        self.side = tk.StringVar(value="BUY")
        tk.Radiobutton(order, text="BUY LONG", variable=self.side, value="BUY", fg="#79c0ff", bg="#161b22", selectcolor="#0d1117", font=("Helvetica", 12, "bold")).grid(row=1, column=0, columnspan=2, pady=8)
        tk.Radiobutton(order, text="SELL SHORT", variable=self.side, value="SELL", fg="#f85149", bg="#161b22", selectcolor="#0d1117", font=("Helvetica", 12, "bold")).grid(row=2, column=0, columnspan=2, pady=5)

        tk.Button(order, text="EXECUTE ORDER", font=("Helvetica", 16, "bold"), bg="#238636", fg="white",
                 command=self.submit_order, relief="flat", pady=15, cursor="hand2").grid(row=3, column=0, columnspan=2, sticky="ew", padx=40, pady=20)

        # Positions
        pos_frame = tk.LabelFrame(right, text=" Open Positions ", font=("Helvetica", 13, "bold"), fg="#58a6ff", bg="#161b22")
        pos_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        cols = ("Symbol", "Size", "Avg", "P&L", "Close")
        self.pos_tree = ttk.Treeview(pos_frame, columns=cols, show="headings", height=6)
        for c in cols[:-1]: self.pos_tree.heading(c, text=c); self.pos_tree.column(c, width=100, anchor="center")
        self.pos_tree.heading("Close", text=""); self.pos_tree.column("Close", width=70)
        self.pos_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.pos_tree.bind("<Button-1>", self.on_position_click)

        # DOM
        dom_frame = tk.LabelFrame(right, text=" DOM • Depth of Market ", font=("Helvetica", 13, "bold"), fg="#58a6ff", bg="#161b22")
        dom_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=20)
        self.dom_tree = ttk.Treeview(dom_frame, columns=("Price","Size","CUM"), show="headings", height=14)
        for col in ("Price","Size","CUM"):
            self.dom_tree.heading(col, text=col)
            self.dom_tree.column(col, width=100, anchor="center" if col=="Price" else "e")
        self.dom_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Time & Sales
        tape_frame = tk.LabelFrame(right, text=" Time & Sales ", font=("Helvetica", 13, "bold"), fg="#58a6ff", bg="#161b22")
        tape_frame.pack(fill=tk.X, padx=20, pady=10)
        self.tape = tk.Listbox(tape_frame, font=("Consolas", 10), height=12, bg="#0d1117", fg="#c9d1d9", selectbackground="#238636")
        self.tape.pack(fill=tk.X, padx=10, pady=10)

        self.redraw_chart()
        self.update_dom()

    def add_100k(self):
        self.cash += 100000
        messagebox.showinfo("Funds Added", "+$100,000 added!\nNew balance: ${:,.0f}".format(self.cash))
        self.update_pnl()

    def add_funds(self):
        amt = simpledialog.askfloat("Add Funds", "Enter amount:", minvalue=1000, parent=self.root)
        if amt:
            self.cash += amt
            messagebox.showinfo("Success", f"${amt:,.0f} added!")
            self.update_pnl()

    def get_margin_used(self):
        return sum(abs(p['size']) * self.sim.data[sym]['price'] / self.LEVERAGE for sym, p in self.positions.items() if p['size'] != 0)

    def get_max_qty(self):
        sym = self.symbol.get()
        price = self.sim.data[sym]['ask']
        margin_avail = self.cash - self.get_margin_used()
        return int((margin_avail * self.LEVERAGE) / price) if price > 0 else 0

    def update_pnl(self):
        if self.in_margin_call:
            return  # Skip during margin call to prevent recursion
        unreal = sum((self.sim.data[sym]['price'] - p['avg_price']) * p['size'] for sym, p in self.positions.items() if p['size'] != 0)
        used_margin = self.get_margin_used()
        free_margin = self.cash + unreal - used_margin
        self.balance_label.config(text=f"Balance: ${self.cash + unreal:,.0f}")
        self.margin_label.config(text=f"Used Margin: ${used_margin:,.0f}")
        self.free_margin_label.config(text=f"Free Margin: ${free_margin:,.0f}", fg="#f85149" if free_margin < 0 else "#79c0ff")
        self.max_qty_label.config(text=f"Max Buy: {self.get_max_qty():,} qty")
        self.pnl_label.config(text=f"P&L: {unreal:+,.0f}", fg="#79c0ff" if unreal >= 0 else "#f85149")

        # Margin call check
        if free_margin < 0:
            self.margin_call()

    def margin_call(self):
        self.in_margin_call = True
        messagebox.showwarning("Margin Call", "Free margin below zero! Liquidating all positions.")
        for sym in list(self.positions.keys()):
            self.close_position(sym, in_margin_call=True)
        self.tape.insert(0, "MARGIN CALL - ALL POSITIONS LIQUIDATED")
        self.tape.itemconfig(0, fg="#f85149")
        self.in_margin_call = False
        self.update_pnl()
        self.update_positions()
        self.redraw_chart()
        self.update_dom()

    def on_position_click(self, event):
        col = self.pos_tree.identify_column(event.x)
        if col == "#5":
            item = self.pos_tree.identify_row(event.y)
            if item:
                sym = self.pos_tree.item(item, "values")[0]
                self.close_position(sym)

    def submit_order(self):
        try:
            sym = self.symbol.get()
            qty_str = self.qty.get().replace(',', '').strip()
            qty = int(qty_str)
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            max_qty = self.get_max_qty()
            if qty > max_qty:
                raise ValueError(f"Max quantity is {max_qty:,}")

            price = self.sim.data[sym]['ask'] if self.side.get() == "BUY" else self.sim.data[sym]['bid']
            impact = (qty / 1000.0) * 0.0055 * (1 if self.side.get() == "BUY" else -1)
            self.sim.data[sym]['volume_pressure'] += impact

            if sym not in self.positions:
                self.positions[sym] = {'size': 0, 'avg_price': 0.0}
            pos = self.positions[sym]
            old_size = pos['size']
            old_cost = pos['avg_price'] * old_size if old_size else 0

            if self.side.get() == "BUY":
                pos['size'] += qty
                pos['avg_price'] = (old_cost + price * qty) / pos['size']
                self.sim.data[sym]['user_bid'] = qty
            else:
                pos['size'] -= qty
                self.sim.data[sym]['user_ask'] = qty

            if pos['size'] == 0:
                del self.positions[sym]
                self.sim.data[sym]['user_bid'] = self.sim.data[sym]['user_ask'] = 0

            color = "#79c0ff" if self.side.get() == "BUY" else "#f85149"
            action = "LONG" if self.side.get() == "BUY" else "SHORT"
            self.tape.insert(0, f"YOU {action} {qty:,} @ {price:.3f}")
            self.tape.itemconfig(0, fg=color)
            self.trade_markers[sym].append((datetime.now(), price, "buy" if self.side.get() == "BUY" else "sell", f"YOU {qty:,}"))

            self.update_positions()
            self.update_pnl()
            self.redraw_chart()
            self.update_dom()

        except ValueError as e:
            messagebox.showerror("Error", str(e))
        # except:
        #     messagebox.showerror("Error", "Invalid quantity format")

    def close_position(self, sym, in_margin_call=False):
        if sym not in self.positions: return
        pos = self.positions[sym]
        exit_price = self.sim.data[sym]['bid']
        pnl = (exit_price - pos['avg_price']) * pos['size']
        self.cash += pnl
        del self.positions[sym]
        self.sim.data[sym]['user_bid'] = self.sim.data[sym]['user_ask'] = 0

        self.tape.insert(0, f"CLOSED {sym} → P&L {pnl:+,.0f}")
        self.tape.itemconfig(0, fg="#ffa657")
        self.trade_markers[sym].append((datetime.now(), exit_price, "close", f"CLOSE {pnl:+,.0f}"))

        if not in_margin_call:
            self.update_positions()
            self.update_pnl()
            self.redraw_chart()
            self.update_dom()

    def update_positions(self):
        for i in self.pos_tree.get_children(): self.pos_tree.delete(i)
        for sym, p in self.positions.items():
            if p['size'] == 0: continue
            cur = self.sim.data[sym]['price']
            unreal = (cur - p['avg_price']) * p['size']
            iid = self.pos_tree.insert("", "end", values=(sym, f"{p['size']:,}", f"{p['avg_price']:.3f}", f"{unreal:+,.0f}", "X"))
            btn = tk.Button(self.pos_tree, text="X", bg="#f85149", fg="white", font=("bold", 10), width=3,
                           command=lambda s=sym: self.close_position(s), relief="flat", cursor="hand2")
            self.pos_tree.window_create(iid, column=4, window=btn)

    def update_dom(self):
        sym = self.symbol.get()
        book = self.sim.generate_book(sym)
        for i in self.dom_tree.get_children(): self.dom_tree.delete(i)
        cum_bid = cum_ask = 0
        for p, s in book['bids']:
            cum_bid += s
            tag = "user" if s == self.sim.data[sym]['user_bid'] else "bid"
            self.dom_tree.insert("", "end", values=(f"{p:.3f}", f"{s:,}", f"{cum_bid:,}"), tags=(tag,))
        for p, s in book['asks']:
            cum_ask += s
            tag = "user" if s == self.sim.data[sym]['user_ask'] else "ask"
            self.dom_tree.insert("", "end", values=(f"{p:.3f}", f"{s:,}", f"{cum_ask:,}"), tags=(tag,))
        self.dom_tree.tag_configure("bid", background="#122a0d", foreground="#79c0ff")
        self.dom_tree.tag_configure("ask", background="#2a0d0d", foreground="#f85149")
        self.dom_tree.tag_configure("user", background="#0d3a1a", foreground="#ffffff", font=("Consolas", 10, "bold"))

    def redraw_chart(self):
        sym = self.symbol.get()
        tf = {"5s":5, "15s":15, "30s":30, "1m":60, "5m":300}[self.timeframe.get()]
        hist = self.sim.get_history(sym, tf)
        if len(hist) < 2: return

        self.ax.clear()
        times = [c['time'] for c in hist]
        dates = [mdates.date2num(t) for t in times]
        width = (dates[-1] - dates[-2]) * 0.9 if len(dates)>1 else 0.0005

        for t, o, h, l, c in zip(dates, [x['open'] for x in hist], [x['high'] for x in hist],
                                 [x['low'] for x in hist], [x['close'] for x in hist]):
            color = '#2ea043' if c >= o else '#f85149'
            self.ax.plot([t, t], [l, h], color=color, linewidth=1.8)
            self.ax.add_patch(Rectangle((t - width/2, min(o,c)), width, abs(c-o) or 0.0001,
                                       facecolor=color, edgecolor=color, alpha=0.9))

        for time, price, typ, _ in self.trade_markers.get(sym, []):
            t_num = mdates.date2num(time)
            marker = 'o' if typ in ["buy","sell"] else 's'
            color = "#79c0ff" if typ == "buy" else "#f85149" if typ == "sell" else "#ffa657"
            self.ax.plot(t_num, price, marker, markersize=11, color=color, alpha=0.9, zorder=15)

        # Bid and Ask lines
        self.ax.axhline(self.sim.data[sym]['bid'], color='#2ea043', ls='--', lw=1.5, label='Bid')
        self.ax.axhline(self.sim.data[sym]['ask'], color='#f85149', ls='--', lw=1.5, label='Ask')

        self.ax.grid(True, alpha=0.3, color="#30363d")
        self.ax.set_title(f"{sym} • {self.timeframe.get().upper()}", fontsize=20, color="#58a6ff", pad=20)
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S' if tf <= 60 else '%H:%M'))
        self.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.2f}"))
        self.ax.tick_params(axis='both', colors='white')  # Ensure white text
        self.canvas.draw()

    def process_queue(self):
        try:
            while True:
                typ, data = self.sim.queue.get_nowait()
                if typ == 'tick' and data == self.symbol.get():
                    self.redraw_chart()
                    self.update_pnl()
                    self.update_positions()  # Added for live positions update
                    self.update_dom()
                elif typ == 'trade':
                    color = "#79c0ff" if data['side'] == 'buy' else "#f85149"
                    msg = f"{data['time']}  {data['sym']:6}  {data['side'].upper():4}  {data['size']:6,} @ {data['price']:8.3f}"
                    self.tape.insert(0, msg)
                    self.tape.itemconfig(0, fg=color)
        except queue.Empty:
            pass
        self.root.after(60, self.process_queue)


if __name__ == "__main__":
    root = tk.Tk()
    app = TradingApp(root)
    root.mainloop()