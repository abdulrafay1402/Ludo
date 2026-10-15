#!/usr/bin/env python3
"""
Ludo AI with Expectimax  (AL-2002 AI Lab project)

GUI game  :  python ludo_ai.py
Simulation:  python ludo_ai.py --sim 200 --depth 1 --types Aggressive Defensive Expectimax Random

Engine rules (kept simple on purpose):
  * Roll a 6 to bring a token out of the yard.
  * Rolling a 6, capturing, or reaching home gives an extra turn.
  * Landing on a non-safe square captures every opponent token there.
  * Safe squares: the 4 start squares and the 4 star squares. Home column is always safe.
  * A token must reach the final square with an exact roll.
"""
import random
import argparse
from collections import Counter

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:  # headless machines can still run --sim
    tk = None

# ----------------------------------------------------------------------------
# ENGINE
# ----------------------------------------------------------------------------
NAMES = ["Red", "Green", "Yellow", "Blue"]
START = [0, 13, 26, 39]                 # absolute start square of each player
SAFE = {0, 13, 26, 39, 8, 21, 34, 47}   # start squares + stars
FINISH = 56                             # rel: -1 yard, 0..50 track, 51..55 home column, 56 done
AI_TYPES = ["Random", "Aggressive", "Defensive", "Expectimax"]


def abs_sq(p, rel):
    return (START[p] + rel) % 52


def next_player(p, active):
    return active[(active.index(p) + 1) % len(active)]


def new_state():
    return tuple(tuple([-1] * 4) for _ in range(4))


def won(state, p):
    return all(r == FINISH for r in state[p])


def legal_moves(state, p, dice):
    moves = []
    for t, r in enumerate(state[p]):
        if r == -1:
            if dice == 6:
                moves.append(t)
        elif r + dice <= FINISH:
            moves.append(t)
    return moves


def apply_move(state, p, t, dice, active):
    """Returns (new_state, extra_turn, captured_count)."""
    r = state[p][t]
    new = 0 if r == -1 else r + dice
    pos = [list(x) for x in state]
    pos[p][t] = new
    captured = 0
    if new <= 50:
        a = abs_sq(p, new)
        if a not in SAFE:
            for q in active:
                if q == p:
                    continue
                for u, rq in enumerate(pos[q]):
                    if 0 <= rq <= 50 and abs_sq(q, rq) == a:
                        pos[q][u] = -1
                        captured += 1
    extra = dice == 6 or captured > 0 or new == FINISH
    return tuple(tuple(x) for x in pos), extra, captured


def in_danger(state, p, rel, active):
    """True if an opponent token is 1-6 squares behind this token."""
    if rel < 0 or rel > 50:
        return False
    a = abs_sq(p, rel)
    if a in SAFE:
        return False
    for q in active:
        if q == p:
            continue
        for rq in state[q]:
            if 0 <= rq <= 50 and 1 <= (a - abs_sq(q, rq)) % 52 <= 6:
                return True
    return False


# ----------------------------------------------------------------------------
# AI PLAYERS
# ----------------------------------------------------------------------------
def player_score(state, p, active):
    s = 0.0
    for r in state[p]:
        if r == -1:
            continue
        if r == FINISH:
            s += 120
            continue
        s += r
        if r > 50:
            s += 10                       # inside the home column
        elif abs_sq(p, r) in SAFE:
            s += 4                        # standing on a safe square
        if in_danger(state, p, r, active):
            s -= 8 + 0.4 * r              # risk of losing progress
    return s


def heuristic(state, me, active):
    if won(state, me):
        return 10000
    for q in active:
        if q != me and won(state, q):
            return -10000
    others = [player_score(state, q, active) for q in active if q != me]
    return player_score(state, me, active) - sum(others) / len(others)


def expectimax(state, p, depth, me, active):
    """p is about to roll. Chance node (dice) -> max node (me) / min node (opponents)."""
    if depth == 0:
        return heuristic(state, me, active)
    total = 0.0
    for dice in range(1, 7):
        moves = legal_moves(state, p, dice)
        if not moves:
            val = expectimax(state, next_player(p, active), depth - 1, me, active)
        else:
            vals = []
            for t in moves:
                ns, extra, _ = apply_move(state, p, t, dice, active)
                if won(ns, p):
                    vals.append(heuristic(ns, me, active))
                else:
                    nxt = p if extra else next_player(p, active)
                    vals.append(expectimax(ns, nxt, depth - 1, me, active))
            val = max(vals) if p == me else min(vals)
        total += val / 6.0
    return total


def choose_expectimax(state, p, dice, active, depth):
    best, best_v = None, -1e18
    for t in legal_moves(state, p, dice):
        ns, extra, _ = apply_move(state, p, t, dice, active)
        if won(ns, p):
            return t
        nxt = p if extra else next_player(p, active)
        v = expectimax(ns, nxt, depth, p, active) + random.random() * 1e-6
        if v > best_v:
            best, best_v = t, v
    return best


def choose_aggressive(state, p, dice, active):
    """Capture > finish > leave yard > push the furthest token."""
    best, best_s = None, -1e18
    for t in legal_moves(state, p, dice):
        ns, _, cap = apply_move(state, p, t, dice, active)
        r, new = state[p][t], ns[p][t]
        s = 100 * cap + (60 if new == FINISH else 0) + (30 if r == -1 else 0) + 0.1 * new
        s += random.random() * 0.01
        if s > best_s:
            best, best_s = t, s
    return best


def choose_defensive(state, p, dice, active):
    """Finish / reach safety / escape danger, avoid risky squares."""
    best, best_s = None, -1e18
    for t in legal_moves(state, p, dice):
        ns, _, cap = apply_move(state, p, t, dice, active)
        r, new = state[p][t], ns[p][t]
        s = 0.0
        if new == FINISH:
            s += 60
        elif new > 50:
            s += 25
        elif abs_sq(p, new) in SAFE:
            s += 30
        if r != -1 and in_danger(state, p, r, active):
            s += 25
        if in_danger(ns, p, new, active):
            s -= 35
        if r == -1:
            s += 20
        s += 10 * cap + 0.05 * new + random.random() * 0.01
        if s > best_s:
            best, best_s = t, s
    return best


def ai_choose(kind, state, p, dice, active, depth=2):
    moves = legal_moves(state, p, dice)
    if kind == "Random":
        return random.choice(moves)
    if kind == "Aggressive":
        return choose_aggressive(state, p, dice, active)
    if kind == "Defensive":
        return choose_defensive(state, p, dice, active)
    return choose_expectimax(state, p, dice, active, depth)


# ----------------------------------------------------------------------------
# HEADLESS SIMULATION
# ----------------------------------------------------------------------------
def play_game(seat_types, depth=1, max_turns=4000):
    active = sorted(seat_types)
    state, p = new_state(), active[0]
    for _ in range(max_turns):
        dice = random.randint(1, 6)
        moves = legal_moves(state, p, dice)
        extra = False
        if moves:
            t = ai_choose(seat_types[p], state, p, dice, active, depth)
            state, extra, _ = apply_move(state, p, t, dice, active)
            if won(state, p):
                return p
        p = p if extra else next_player(p, active)
    return None


def simulate(types, n, depth):
    wins, draws = Counter(), 0
    for i in range(n):
        seats = list(types)
        random.shuffle(seats)               # rotate seats so no colour is favoured
        seat_types = {p: seats[p] for p in range(len(seats))}
        w = play_game(seat_types, depth)
        if w is None:
            draws += 1
        else:
            wins[seat_types[w]] += 1
        if (i + 1) % 25 == 0:
            print(f"  ... {i + 1}/{n} games")
    print(f"\nResults over {n} games ({len(types)} players, Expectimax depth {depth})")
    print(f"{'Agent':<12}{'Wins':>6}{'Win %':>8}")
    for k in sorted(set(types), key=lambda x: -wins[x]):
        share = wins[k] / max(1, types.count(k))   # per-seat wins if a type repeats
        print(f"{k:<12}{wins[k]:>6}{100 * wins[k] / n:>7.1f}%"
              + (f"   ({types.count(k)} seats)" if types.count(k) > 1 else ""))
    if draws:
        print(f"Unfinished games: {draws}")


# ----------------------------------------------------------------------------
# TKINTER GUI
# ----------------------------------------------------------------------------
CELL = 40
COLORS = ["#e74c3c", "#2ecc71", "#f1c40f", "#3498db"]
LIGHT = ["#f5b7b1", "#abebc6", "#f9e79f", "#aed6f1"]


def build_track():
    t = []
    t += [(6, c) for c in range(1, 6)]
    t += [(r, 6) for r in range(5, -1, -1)]
    t += [(0, 7), (0, 8)]
    t += [(r, 8) for r in range(1, 6)]
    t += [(6, c) for c in range(9, 15)]
    t += [(7, 14), (8, 14)]
    t += [(8, c) for c in range(13, 8, -1)]
    t += [(r, 8) for r in range(9, 15)]
    t += [(14, 7), (14, 6)]
    t += [(r, 6) for r in range(13, 8, -1)]
    t += [(8, c) for c in range(5, -1, -1)]
    t += [(7, 0), (6, 0)]
    assert len(t) == 52
    return t


TRACK = build_track()
HOME_COL = [
    [(7, c) for c in range(1, 6)],
    [(r, 7) for r in range(1, 6)],
    [(7, c) for c in range(13, 8, -1)],
    [(r, 7) for r in range(13, 8, -1)],
]
YARD = [
    [(1, 1), (1, 4), (4, 1), (4, 4)],
    [(1, 10), (1, 13), (4, 10), (4, 13)],
    [(10, 10), (10, 13), (13, 10), (13, 13)],
    [(10, 1), (10, 4), (13, 1), (13, 4)],
]
QUAD = [(0, 0), (0, 9), (9, 9), (9, 0)]          # top-left cell of each yard quadrant
DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1)]        # where finished tokens sit in the centre


def token_cell(p, rel, t):
    if rel == -1:
        return YARD[p][t]
    if rel <= 50:
        return TRACK[abs_sq(p, rel)]
    if rel < FINISH:
        return HOME_COL[p][rel - 51]
    return (7, 7)


class LudoApp:
    def __init__(self, root):
        self.root = root
        root.title("Ludo AI - Expectimax")
        self.gid = 0
        self.phase = "over"
        self.state = new_state()
        self.active, self.types = [], {}
        self.turn, self.dice, self.moves = 0, 0, []

        top = ttk.Frame(root)
        top.pack(padx=8, pady=6, fill="x")
        defaults = ["Human", "Expectimax", "Aggressive", "Defensive"]
        self.seat_vars = []
        for p in range(4):
            tk.Label(top, text=NAMES[p], fg=COLORS[p], font=("Arial", 10, "bold")).grid(row=0, column=2 * p)
            v = tk.StringVar(value=defaults[p])
            ttk.Combobox(top, textvariable=v, width=10, state="readonly",
                         values=["Human"] + AI_TYPES + ["None"]).grid(row=0, column=2 * p + 1, padx=(2, 8))
            self.seat_vars.append(v)
        tk.Label(top, text="Depth").grid(row=0, column=8)
        self.depth_var = tk.IntVar(value=2)
        ttk.Spinbox(top, from_=0, to=3, width=3, textvariable=self.depth_var).grid(row=0, column=9, padx=4)
        ttk.Button(top, text="New Game", command=self.new_game).grid(row=0, column=10, padx=6)

        self.canvas = tk.Canvas(root, width=15 * CELL, height=15 * CELL, bg="white", highlightthickness=0)
        self.canvas.pack(padx=8)
        self.canvas.bind("<Button-1>", self.on_click)

        bar = ttk.Frame(root)
        bar.pack(fill="x", padx=8, pady=4)
        self.roll_btn = ttk.Button(bar, text="Roll Dice", command=self.human_roll, state="disabled")
        self.roll_btn.pack(side="left")
        self.dice_lbl = tk.Label(bar, text="Dice: -", font=("Arial", 16, "bold"), width=10)
        self.dice_lbl.pack(side="left", padx=10)
        self.status = tk.Label(bar, text="Press New Game", anchor="w")
        self.status.pack(side="left", fill="x", expand=True)

        self.logbox = tk.Text(root, height=7, width=70, state="disabled")
        self.logbox.pack(padx=8, pady=(0, 8), fill="x")
        self.redraw()

    # ---- helpers ---------------------------------------------------------
    def log(self, msg):
        self.logbox.config(state="normal")
        self.logbox.insert("end", msg + "\n")
        self.logbox.see("end")
        self.logbox.config(state="disabled")

    def later(self, ms, fn):
        gid = self.gid
        self.root.after(ms, lambda: fn() if gid == self.gid else None)

    # ---- game flow -------------------------------------------------------
    def new_game(self):
        types = {p: v.get() for p, v in enumerate(self.seat_vars) if v.get() != "None"}
        if len(types) < 2:
            messagebox.showerror("Ludo", "Pick at least 2 players.")
            return
        self.gid += 1
        self.types, self.active = types, sorted(types)
        self.state, self.turn, self.moves, self.dice = new_state(), self.active[0], [], 0
        self.logbox.config(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.config(state="disabled")
        self.dice_lbl.config(text="Dice: -")
        self.log("New game started.")
        self.redraw()
        self.start_turn()

    def start_turn(self):
        p = self.turn
        self.status.config(text=f"{NAMES[p]}'s turn ({self.types[p]})", fg=COLORS[p])
        if self.types[p] == "Human":
            self.phase = "roll"
            self.roll_btn.config(state="normal")
        else:
            self.phase = "busy"
            self.roll_btn.config(state="disabled")
            self.later(600, self.ai_turn)

    def roll_dice(self):
        self.dice = random.randint(1, 6)
        self.dice_lbl.config(text=f"Dice: {self.dice}")
        self.moves = legal_moves(self.state, self.turn, self.dice)
        self.root.update_idletasks()

    def human_roll(self):
        if self.phase != "roll":
            return
        self.phase = "busy"
        self.roll_btn.config(state="disabled")
        self.roll_dice()
        p = self.turn
        if not self.moves:
            self.log(f"{NAMES[p]} rolled {self.dice}: no legal move.")
            self.later(700, lambda: self.advance(False))
        elif len(self.moves) == 1 or len({self.state[p][t] for t in self.moves}) == 1:
            self.do_move(self.moves[0])
        else:
            self.phase = "pick"
            self.status.config(text=f"{NAMES[p]}: click a highlighted token")
            self.redraw()

    def ai_turn(self):
        p = self.turn
        self.roll_dice()
        if not self.moves:
            self.log(f"{NAMES[p]} ({self.types[p]}) rolled {self.dice}: no legal move.")
            self.later(700, lambda: self.advance(False))
            return
        t = ai_choose(self.types[p], self.state, p, self.dice, self.active, self.depth_var.get())
        self.do_move(t)

    def do_move(self, t):
        p, dice = self.turn, self.dice
        before = self.state[p][t]
        self.state, extra, cap = apply_move(self.state, p, t, dice, self.active)
        after = self.state[p][t]
        what = "leaves the yard" if before == -1 else ("reaches HOME" if after == FINISH else f"moves to step {after}")
        msg = f"{NAMES[p]} rolled {dice}: token {t + 1} {what}"
        if cap:
            msg += f" and captures {cap} token(s)!"
        self.log(msg)
        self.moves, self.phase = [], "busy"
        self.redraw()
        if won(self.state, p):
            self.phase = "over"
            self.status.config(text=f"{NAMES[p]} WINS!", fg=COLORS[p])
            self.log(f"*** {NAMES[p]} ({self.types[p]}) wins the game! ***")
            messagebox.showinfo("Ludo", f"{NAMES[p]} ({self.types[p]}) wins!")
            return
        self.later(500, lambda: self.advance(extra))

    def advance(self, extra):
        if not extra:
            self.turn = next_player(self.turn, self.active)
        self.redraw()
        self.start_turn()

    def on_click(self, e):
        if self.phase != "pick":
            return
        cell = (e.y // CELL, e.x // CELL)
        for t in self.moves:
            if token_cell(self.turn, self.state[self.turn][t], t) == cell:
                self.do_move(t)
                return

    # ---- drawing ---------------------------------------------------------
    def rect(self, r, c, fill, outline="#999"):
        self.canvas.create_rectangle(c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL, fill=fill, outline=outline)

    def redraw(self):
        cv = self.canvas
        cv.delete("all")
        for p in range(4):
            r0, c0 = QUAD[p]
            col = LIGHT[p] if p in self.active or not self.active else "#dddddd"
            cv.create_rectangle(c0 * CELL, r0 * CELL, (c0 + 6) * CELL, (r0 + 6) * CELL, fill=col, outline="#777")
            for (r, c) in YARD[p]:
                cv.create_oval(c * CELL + 4, r * CELL + 4, (c + 1) * CELL - 4, (r + 1) * CELL - 4,
                               fill="white", outline="#999")
        cv.create_rectangle(6 * CELL, 6 * CELL, 9 * CELL, 9 * CELL, fill="#eeeeee", outline="#777")
        cv.create_text(7.5 * CELL, 7.5 * CELL, text="HOME", font=("Arial", 9, "bold"), fill="#888")
        for i, (r, c) in enumerate(TRACK):
            self.rect(r, c, "white")
            if i in START:
                self.rect(r, c, COLORS[START.index(i)])
            elif i in SAFE:
                cv.create_text(c * CELL + CELL / 2, r * CELL + CELL / 2, text="*", font=("Arial", 18, "bold"), fill="#888")
        for p in range(4):
            for (r, c) in HOME_COL[p]:
                self.rect(r, c, COLORS[p])

        stack = {}
        for p in self.active:
            for t in range(4):
                rel = self.state[p][t]
                r, c = token_cell(p, rel, t)
                cx, cy = c * CELL + CELL / 2, r * CELL + CELL / 2
                rad, wd, outline = 13, 2, "black"
                if rel == FINISH:
                    dx, dy = DIRS[p]
                    cx = 7.5 * CELL + dx * 30 + (t % 2) * 11 - 5
                    cy = 7.5 * CELL + dy * 30 + (t // 2) * 11 - 5
                    rad = 6
                elif rel != -1:
                    k = stack.get((r, c), 0)
                    stack[(r, c)] = k + 1
                    cx += k * 6 - 3 * (k > 0)
                    cy -= k * 6 - 3 * (k > 0)
                if self.phase == "pick" and p == self.turn and t in self.moves:
                    wd, outline = 4, "#ff00ff"
                cv.create_oval(cx - rad, cy - rad, cx + rad, cy + rad, fill=COLORS[p], outline=outline, width=wd)
                if rad > 6:
                    cv.create_text(cx, cy, text=str(t + 1), font=("Arial", 9, "bold"))


def run_gui():
    if tk is None:
        raise SystemExit("Tkinter is not available. Use --sim for headless mode.")
    root = tk.Tk()
    LudoApp(root)
    root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", type=int, default=0, help="run N headless games instead of the GUI")
    ap.add_argument("--depth", type=int, default=1, help="Expectimax depth for simulation")
    ap.add_argument("--types", nargs="+", default=["Aggressive", "Defensive", "Expectimax", "Random"],
                    choices=AI_TYPES)
    a = ap.parse_args()
    if a.sim:
        simulate(a.types, a.sim, a.depth)
    else:
        run_gui()