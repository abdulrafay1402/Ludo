#!/usr/bin/env python3
"""
Ludo AI with Expectimax (AL-2002 AI Lab project) -- OOP + Tkinter + NumPy

Run:      python ludo.py (Tkinter GUI)
Simulate: python ludo.py --sim 200 --depth 1 --types Aggressive Defensive Expectimax Random

Engine rules:
  * Roll a 6 to bring a token out of the yard.
  * Rolling a 6, capturing, or reaching home gives an extra turn.
  * Landing on a non-safe square captures every opponent token there.
  * Safe squares: the 4 start squares and the 4 star squares. Home column is always safe.
  * A token must reach the final square with an exact roll.
"""
import sys
import random
import argparse
from collections import Counter

import numpy as np

# ----------------------------------------------------------------------------
# Pygame import (guarded so --sim works on headless boxes)
# ----------------------------------------------------------------------------
try:
    import pygame
    pygame_available = True
except Exception:
    pygame = None
    pygame_available = False


# ============================================================================
# CONSTANTS
# ============================================================================
NAMES = ["Red", "Green", "Yellow", "Blue"]
START = np.array([0, 13, 26, 39], dtype=np.int32)
SAFE = np.array([0, 13, 26, 39, 8, 21, 34, 47], dtype=np.int32)
FINISH = 56

YARD, TRACK, HOME_COL = -1, 0, 51
AI_TYPES = ["Random", "Aggressive", "Defensive", "Expectimax"]
PLAYER_MODES = ["Human"] + AI_TYPES + ["None"]

# Legacy Pygame visuals; the default desktop interface is in tkinter_ui.py.
CELL = 44
MARGIN = 20
BOARD_PX = 15 * CELL
SIDEBAR_W = 300
WIN_W = BOARD_PX + 2 * MARGIN + SIDEBAR_W
WIN_H = BOARD_PX + 2 * MARGIN

COLORS = [(231, 76, 60), (46, 204, 113), (241, 196, 15), (52, 152, 219)]
LIGHT  = [(245, 183, 177), (171, 235, 198), (249, 231, 159), (174, 214, 241)]
BLACK, WHITE, GREY, DARK = (0, 0, 0), (255, 255, 255), (150, 150, 150), (40, 40, 40)
HILITE = (255, 0, 255)
BG = (245, 245, 245)


# ============================================================================
# BOARD GEOMETRY
# ============================================================================
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
YARD_CELLS = [
    [(1, 1), (1, 4), (4, 1), (4, 4)],
    [(1, 10), (1, 13), (4, 10), (4, 13)],
    [(10, 10), (10, 13), (13, 10), (13, 13)],
    [(10, 1), (10, 4), (13, 1), (13, 4)],
]
QUAD = [(0, 0), (0, 9), (9, 9), (9, 0)]
DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1)]


def token_cell(p, rel, t):
    if rel == YARD:
        return YARD_CELLS[p][t]
    if rel <= 50:
        return TRACK[(int(START[p]) + rel) % 52]
    if rel < FINISH:
        return HOME_COL[p][rel - 51]
    return (7, 7)


# ============================================================================
# OOP ENGINE
# ============================================================================
def next_player(p, active):
    return active[(active.index(p) + 1) % len(active)]


class Board:
    """Owns Ludo rules. State is a NumPy (4, 4) int32 array."""

    @staticmethod
    def new_state():
        return np.full((4, 4), YARD, dtype=np.int32)

    @staticmethod
    def abs_sq(p, rel):
        return int((START[p] + rel) % 52)

    @staticmethod
    def won(state, p):
        return bool(np.all(state[p] == FINISH))

    @staticmethod
    def legal_moves(state, p, dice):
        row = state[p]
        moves = []
        for t in range(4):
            r = int(row[t])
            if r == YARD:
                if dice == 6:
                    moves.append(t)
            elif r + dice <= FINISH:
                moves.append(t)
        return moves

    @staticmethod
    def apply_move(state, p, t, dice, active):
        """Returns (new_state, extra_turn, captured_count). No in-place mutation."""
        new_state = state.copy()
        r = int(state[p, t])
        new = 0 if r == YARD else r + dice
        new_state[p, t] = new
        captured = 0
        if new <= 50:
            a = Board.abs_sq(p, new)
            if a not in SAFE:
                for q in active:
                    if q == p:
                        continue
                    for u in range(4):
                        rq = int(new_state[q, u])
                        if 0 <= rq <= 50 and Board.abs_sq(q, rq) == a:
                            new_state[q, u] = YARD
                            captured += 1
        extra = (dice == 6) or (captured > 0) or (new == FINISH)
        return new_state, extra, captured

    @staticmethod
    def in_danger(state, p, rel, active):
        if rel < 0 or rel > 50:
            return False
        a = Board.abs_sq(p, rel)
        if a in SAFE:
            return False
        for q in active:
            if q == p:
                continue
            for rq in state[q]:
                rq = int(rq)
                if 0 <= rq <= 50 and 1 <= (a - Board.abs_sq(q, rq)) % 52 <= 6:
                    return True
        return False


class AIContext:
    """Bundles shared AI info: active seats and search depth."""
    def __init__(self, active, depth=1):
        self.active = list(active)
        self.depth = depth


class Player:
    """Abstract base for every seat."""
    is_human = False

    def __init__(self, index, name):
        self.index = index
        self.name = name

    def choose(self, state, dice, ctx):
        raise NotImplementedError


class HumanPlayer(Player):
    is_human = True

    def choose(self, state, dice, ctx):
        return None  # GUI supplies the move


class RandomAI(Player):
    def choose(self, state, dice, ctx):
        return random.choice(Board.legal_moves(state, self.index, dice))


# --- shared heuristic used by Expectimax ----------------------------------
def player_score(state, p, active):
    s = 0.0
    for r in state[p]:
        r = int(r)
        if r == YARD:
            continue
        if r == FINISH:
            s += 120
            continue
        s += r
        if r > 50:
            s += 10
        elif Board.abs_sq(p, r) in SAFE:
            s += 4
        if Board.in_danger(state, p, r, active):
            s -= 8 + 0.4 * r
    return s


def heuristic(state, me, active):
    if Board.won(state, me):
        return 10000
    for q in active:
        if q != me and Board.won(state, q):
            return -10000
    others = [player_score(state, q, active) for q in active if q != me]
    return player_score(state, me, active) - sum(others) / len(others)


def expectimax(state, p, depth, me, active):
    if depth == 0:
        return heuristic(state, me, active)
    total = 0.0
    for dice in range(1, 7):
        moves = Board.legal_moves(state, p, dice)
        if not moves:
            val = expectimax(state, next_player(p, active), depth - 1, me, active)
        else:
            vals = []
            for t in moves:
                ns, extra, _ = Board.apply_move(state, p, t, dice, active)
                if Board.won(ns, p):
                    vals.append(heuristic(ns, me, active))
                else:
                    nxt = p if extra else next_player(p, active)
                    vals.append(expectimax(ns, nxt, depth - 1, me, active))
            val = max(vals) if p == me else min(vals)
        total += val / 6.0
    return total


class AggressiveAI(Player):
    """Capture > finish > leave yard > push the furthest token."""
    def choose(self, state, dice, ctx):
        best, best_s = None, -1e18
        for t in Board.legal_moves(state, self.index, dice):
            ns, _, cap = Board.apply_move(state, self.index, t, dice, ctx.active)
            r, new = int(state[self.index, t]), int(ns[self.index, t])
            s = (100 * cap
                 + (60 if new == FINISH else 0)
                 + (30 if r == YARD else 0)
                 + 0.1 * new
                 + random.random() * 0.01)
            if s > best_s:
                best, best_s = t, s
        return best


class DefensiveAI(Player):
    """Finish / reach safety / escape danger, avoid risky squares."""
    def choose(self, state, dice, ctx):
        best, best_s = None, -1e18
        for t in Board.legal_moves(state, self.index, dice):
            ns, _, cap = Board.apply_move(state, self.index, t, dice, ctx.active)
            r, new = int(state[self.index, t]), int(ns[self.index, t])
            s = 0.0
            if new == FINISH:
                s += 60
            elif new > 50:
                s += 25
            elif Board.abs_sq(self.index, new) in SAFE:
                s += 30
            if r != YARD and Board.in_danger(state, self.index, r, ctx.active):
                s += 25
            if Board.in_danger(ns, self.index, new, ctx.active):
                s -= 35
            if r == YARD:
                s += 20
            s += 10 * cap + 0.05 * new + random.random() * 0.01
            if s > best_s:
                best, best_s = t, s
        return best


class ExpectimaxAI(Player):
    def choose(self, state, dice, ctx):
        best, best_v = None, -1e18
        for t in Board.legal_moves(state, self.index, dice):
            ns, extra, _ = Board.apply_move(state, self.index, t, dice, ctx.active)
            if Board.won(ns, self.index):
                return t
            nxt = self.index if extra else next_player(self.index, ctx.active)
            v = expectimax(ns, nxt, ctx.depth, self.index, ctx.active) + random.random() * 1e-6
            if v > best_v:
                best, best_v = t, v
        return best


AI_REGISTRY = {
    "Random":     RandomAI,
    "Aggressive": AggressiveAI,
    "Defensive":  DefensiveAI,
    "Expectimax": ExpectimaxAI,
}


def make_player(mode, index):
    if mode == "Human":
        return HumanPlayer(index, NAMES[index])
    return AI_REGISTRY[mode](index, NAMES[index])


# ============================================================================
# GAME ORCHESTRATOR
# ============================================================================
class LudoGame:
    """Pure logic (no rendering). Shared by GUI and --sim."""

    def __init__(self, modes, depth=1):
        """modes: dict {seat_index: mode_string}."""
        self.modes = dict(modes)
        self.active = sorted(self.modes)
        self.players = {p: make_player(self.modes[p], p) for p in self.active}
        self.state = Board.new_state()
        self.turn = self.active[0]
        self.ctx = AIContext(self.active, depth)

    def roll(self):
        return random.randint(1, 6)

    def legal(self, dice):
        return Board.legal_moves(self.state, self.turn, dice)

    def ai_choose(self, dice):
        return self.players[self.turn].choose(self.state, dice, self.ctx)

    def apply(self, t, dice):
        self.state, extra, cap = Board.apply_move(self.state, self.turn, t, dice, self.ctx.active)
        return extra, cap

    def advance(self, extra):
        if not extra:
            self.turn = next_player(self.turn, self.ctx.active)

    def winner(self):
        for p in self.active:
            if Board.won(self.state, p):
                return p
        return None


def play_game(modes, depth=1, max_turns=4000):
    g = LudoGame(modes, depth)
    for _ in range(max_turns):
        dice = g.roll()
        moves = g.legal(dice)
        extra = False
        if moves:
            t = g.ai_choose(dice)
            if t is None:
                t = random.choice(moves)
            extra, _ = g.apply(t, dice)
            if g.winner() is not None:
                return g.winner()
        g.advance(extra)
    return None


def simulate(types, n, depth):
    wins = Counter()
    draws = 0
    win_matrix = np.zeros(len(types), dtype=np.int32)   # NumPy use
    for i in range(n):
        seats = list(types)
        random.shuffle(seats)
        modes = {p: seats[p] for p in range(len(seats))}
        w = play_game(modes, depth)
        if w is None:
            draws += 1
        else:
            wins[modes[w]] += 1
            win_matrix[w] += 1
        if (i + 1) % 25 == 0:
            print(f"  ... {i + 1}/{n} games")
    print(f"\nResults over {n} games ({len(types)} players, Expectimax depth {depth})")
    print(f"{'Agent':<12}{'Wins':>6}{'Win %':>8}")
    for k in sorted(set(types), key=lambda x: -wins[x]):
        print(f"{k:<12}{wins[k]:>6}{100 * wins[k] / n:>7.1f}%"
              + (f"   ({types.count(k)} seats)" if types.count(k) > 1 else ""))
    if draws:
        print(f"Unfinished games: {draws}")


# ============================================================================
# LEGACY PYGAME GUI
# ============================================================================
class Button:
    def __init__(self, rect, text, callback, font):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.font = font
        self.hover = False

    def draw(self, surf):
        col = (205, 205, 205) if self.hover else (175, 175, 175)
        pygame.draw.rect(surf, col, self.rect, border_radius=6)
        pygame.draw.rect(surf, DARK, self.rect, 2, border_radius=6)
        label = self.font.render(self.text, True, DARK)
        surf.blit(label, label.get_rect(center=self.rect.center))

    def handle(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.callback()


class SetupScreen:
    """Pre-game menu: number of opponents and mode for each seat."""

    def __init__(self, app):
        self.app = app
        self.font = pygame.font.SysFont("Arial", 20, bold=True)
        self.small = pygame.font.SysFont("Arial", 16)
        self.big = pygame.font.SysFont("Arial", 30, bold=True)

        self.num_players = 4
        self.modes = {0: "Human", 1: "Expectimax", 2: "Aggressive", 3: "Defensive"}
        self.depth = 2

        self.buttons = []
        self._build_buttons()

    def _build_buttons(self):
        self.buttons.clear()
        # Player-count buttons
        for i, n in enumerate([2, 3, 4]):
            x = 60 + i * 150
            self.buttons.append(Button((x, 130, 130, 46), f"{n} Players",
                                       lambda n=n: self.set_count(n), self.font))
        # Depth buttons
        for i, d in enumerate([0, 1, 2, 3]):
            x = 60 + i * 100
            self.buttons.append(Button((x, 480, 80, 40), f"d={d}",
                                       lambda d=d: self.set_depth(d), self.font))
        # Per-seat mode cyclers
        for p in range(4):
            y = 220 + p * 55
            self.buttons.append(Button((340, y, 220, 42), "",
                                       lambda p=p: self.cycle_mode(p), self.small))
        # Start
        self.buttons.append(Button((WIN_W // 2 - 100, WIN_H - 70, 200, 50),
                                   "START GAME", self.start, self.big))

    def set_count(self, n):
        self.num_players = n
        for p in range(4):
            if p >= n:
                self.modes[p] = "None"
            elif self.modes.get(p, "None") == "None":
                # Fill newly-activated seats with a sensible default
                self.modes[p] = "Human" if p == 0 else AI_TYPES[(p - 1) % len(AI_TYPES)]
        if self.modes.get(0, "None") == "None":
            self.modes[0] = "Human"

    def set_depth(self, d):
        self.depth = d

    def cycle_mode(self, p):
        if p >= self.num_players:
            return
        cur = self.modes.get(p, "None")
        idx = PLAYER_MODES.index(cur)
        self.modes[p] = PLAYER_MODES[(idx + 1) % len(PLAYER_MODES)]

    def start(self):
        active_modes = {p: m for p, m in self.modes.items() if m != "None"}
        if len(active_modes) < 2:
            self.app.flash = "Pick at least 2 players!"
            return
        self.app.start_game(active_modes, self.depth)

    def draw(self, surf):
        surf.fill(BG)
        title = self.big.render("Ludo AI - Setup", True, DARK)
        surf.blit(title, title.get_rect(center=(WIN_W // 2, 50)))

        surf.blit(self.font.render("Number of players", True, DARK), (60, 100))
        surf.blit(self.font.render("Assign a mode to each seat (click to cycle)", True, DARK), (340, 180))

        for p in range(4):
            y = 220 + p * 55
            tag = self.font.render(NAMES[p], True, COLORS[p])
            surf.blit(tag, (240, y + 10))
            mode = self.modes.get(p, "None") if p < self.num_players else "None"
            # update the button label and draw
            for b in self.buttons:
                if b.rect.topleft == (340, y):
                    b.text = mode
                    break

        surf.blit(self.font.render("Expectimax depth", True, DARK), (60, 450))

        # Draw all buttons, highlighting current selections
        for b in self.buttons:
            if b.text.startswith(f"{self.num_players} "):
                pygame.draw.rect(surf, (120, 200, 120), b.rect, border_radius=6)
            if b.text == f"d={self.depth}":
                pygame.draw.rect(surf, (120, 200, 120), b.rect, border_radius=6)
            b.draw(surf)

        if getattr(self.app, "flash", None):
            msg = self.font.render(self.app.flash, True, (200, 0, 0))
            surf.blit(msg, msg.get_rect(center=(WIN_W // 2, WIN_H - 30)))

    def handle(self, event):
        for b in self.buttons:
            b.handle(event)

    def update(self):
        pass


class PlayScreen:
    def __init__(self, app, modes, depth):
        self.app = app
        self.font = pygame.font.SysFont("Arial", 16, bold=True)
        self.big = pygame.font.SysFont("Arial", 22, bold=True)
        self.game = LudoGame(modes, depth)
        self.dice = 0
        self.moves = []
        self.phase = "roll"      # roll / pick / busy / over
        self.log = []
        self.pending_extra = False
        self.timer = 0
        self.rolled_this_turn = False

        side_x = BOARD_PX + MARGIN * 2
        self.roll_button = Button((side_x, MARGIN + 300, 200, 50),
                                  "Roll Dice", self.human_roll, self.font)
        self._begin_turn()

    # -- logging -----------------------------------------------------------
    def add_log(self, msg):
        self.log.append(msg)
        self.log = self.log[-9:]

    # -- turn lifecycle ----------------------------------------------------
    def _begin_turn(self):
        p = self.game.turn
        player = self.game.players[p]
        self.moves = []
        self.dice = 0
        self.rolled_this_turn = False
        if player.is_human:
            self.phase = "roll"
        else:
            self.phase = "busy"
            self.timer = pygame.time.get_ticks() + 500

    def human_roll(self):
        if self.phase != "roll":
            return
        self.phase = "busy"
        self._roll_and_branch()

    def _roll_and_branch(self):
        self.dice = self.game.roll()
        self.rolled_this_turn = True
        p = self.game.turn
        self.moves = self.game.legal(self.dice)
        if not self.moves:
            self.add_log(f"{NAMES[p]} rolled {self.dice}: no move")
            self.pending_extra = False
            self.timer = pygame.time.get_ticks() + 500
            self.phase = "busy"
        elif len(self.moves) == 1:
            self._do_move(self.moves[0])
        else:
            if self.game.players[p].is_human:
                self.phase = "pick"
            else:
                self.phase = "busy"
                self.timer = pygame.time.get_ticks() + 300

    def _ai_step(self):
        p = self.game.turn
        if not self.rolled_this_turn:
            self._roll_and_branch()
            return
        if not self.moves:
            self.pending_extra = False
            self.timer = pygame.time.get_ticks() + 300
            return
        t = self.game.players[p].choose(self.game.state, self.dice, self.game.ctx)
        if t is None:
            t = random.choice(self.moves)
        self._do_move(t)

    def _do_move(self, t):
        p = self.game.turn
        before = int(self.game.state[p, t])
        extra, cap = self.game.apply(t, self.dice)
        after = int(self.game.state[p, t])
        what = ("leaves the yard" if before == YARD
                else ("reaches HOME" if after == FINISH else f"to step {after}"))
        msg = f"{NAMES[p]} rolled {self.dice}: token {t + 1} {what}"
        if cap:
            msg += f"  (+{cap} capture!)"
        self.add_log(msg)
        self.moves = []
        w = self.game.winner()
        if w is not None:
            self.phase = "over"
            self.app.game_over(w, self.game.modes[w])
            return
        self.pending_extra = extra
        self.dice = 0
        self.rolled_this_turn = False
        self.timer = pygame.time.get_ticks() + 450
        self.phase = "busy"

    def advance_turn(self):
        if not self.pending_extra:
            self.game.advance(False)
        self._begin_turn()

    # -- events ------------------------------------------------------------
    def handle(self, event):
        if self.phase == "roll":
            self.roll_button.handle(event)
        elif self.phase == "pick" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            col = (mx - MARGIN) // CELL
            row = (my - MARGIN) // CELL
            p = self.game.turn
            for t in self.moves:
                if token_cell(p, int(self.game.state[p, t]), t) == (row, col):
                    self._do_move(t)
                    return

    # -- update ------------------------------------------------------------
    def update(self):
        if self.phase == "over":
            return
        now = pygame.time.get_ticks()
        if self.phase == "busy" and now >= self.timer:
            p = self.game.turn
            if self.game.players[p].is_human:
                # Human with no moves already handled; otherwise wait for input
                if not self.rolled_this_turn:
                    self.phase = "roll"
                    return
                if not self.moves:
                    self.advance_turn()
            else:
                if not self.rolled_this_turn:
                    self._roll_and_branch()
                elif self.moves:
                    self._ai_step()
                else:
                    self.advance_turn()

    # -- drawing -----------------------------------------------------------
    def _rect(self, surf, r, c, fill):
        pygame.draw.rect(surf, fill,
                         (MARGIN + c * CELL, MARGIN + r * CELL, CELL, CELL))
        pygame.draw.rect(surf, GREY,
                         (MARGIN + c * CELL, MARGIN + r * CELL, CELL, CELL), 1)

    def draw(self, surf):
        surf.fill(WHITE)
        # Quadrants
        for p in range(4):
            r0, c0 = QUAD[p]
            col = LIGHT[p] if p in self.game.active else (225, 225, 225)
            pygame.draw.rect(surf, col,
                             (MARGIN + c0 * CELL, MARGIN + r0 * CELL, 6 * CELL, 6 * CELL))
            pygame.draw.rect(surf, GREY,
                             (MARGIN + c0 * CELL, MARGIN + r0 * CELL, 6 * CELL, 6 * CELL), 2)
            for (r, c) in YARD_CELLS[p]:
                cx = MARGIN + c * CELL + CELL // 2
                cy = MARGIN + r * CELL + CELL // 2
                pygame.draw.circle(surf, WHITE, (cx, cy), CELL // 2 - 5)
                pygame.draw.circle(surf, GREY, (cx, cy), CELL // 2 - 5, 1)

        # Centre
        pygame.draw.rect(surf, (235, 235, 235),
                         (MARGIN + 6 * CELL, MARGIN + 6 * CELL, 3 * CELL, 3 * CELL))
        pygame.draw.rect(surf, GREY,
                         (MARGIN + 6 * CELL, MARGIN + 6 * CELL, 3 * CELL, 3 * CELL), 2)

        # Track
        for i, (r, c) in enumerate(TRACK):
            fill = WHITE
            if i in START:
                fill = COLORS[int(np.where(START == i)[0][0])]
            self._rect(surf, r, c, fill)
            if i in SAFE and i not in START:
                cx = MARGIN + c * CELL + CELL // 2
                cy = MARGIN + r * CELL + CELL // 2
                pygame.draw.circle(surf, GREY, (cx, cy), 6, 2)

        # Home columns
        for p in range(4):
            for (r, c) in HOME_COL[p]:
                self._rect(surf, r, c, COLORS[p])

        # Tokens
        stack = {}
        for p in self.game.active:
            for t in range(4):
                rel = int(self.game.state[p, t])
                r, c = token_cell(p, rel, t)
                cx = MARGIN + c * CELL + CELL // 2
                cy = MARGIN + r * CELL + CELL // 2
                rad, outline_w, outline = 14, 2, BLACK
                if rel == FINISH:
                    dx, dy = DIRS[p]
                    cx = MARGIN + int(7.5 * CELL) + dx * 30 + (t % 2) * 12 - 6
                    cy = MARGIN + int(7.5 * CELL) + dy * 30 + (t // 2) * 12 - 6
                    rad = 7
                elif rel != YARD:
                    k = stack.get((r, c), 0)
                    stack[(r, c)] = k + 1
                    if k:
                        cx += (k % 2) * 8 - 4
                        cy += (k // 2) * 8 - 4
                if self.phase == "pick" and p == self.game.turn and t in self.moves:
                    outline_w, outline = 4, HILITE
                pygame.draw.circle(surf, COLORS[p], (cx, cy), rad)
                pygame.draw.circle(surf, outline, (cx, cy), rad, outline_w)
                if rad > 8:
                    label = self.font.render(str(t + 1), True, BLACK)
                    surf.blit(label, label.get_rect(center=(cx, cy)))

        # Sidebar
        side_x = BOARD_PX + MARGIN * 2
        p = self.game.turn
        header = self.big.render(f"{NAMES[p]} ({self.game.modes[p]})", True, COLORS[p])
        surf.blit(header, (side_x, MARGIN))
        dice_txt = self.big.render(f"Dice: {self.dice if self.dice else '-'}", True, DARK)
        surf.blit(dice_txt, (side_x, MARGIN + 40))

        if self.phase == "roll":
            self.roll_button.draw(surf)
        elif self.phase == "pick":
            hint = self.font.render("Click a highlighted token", True, HILITE)
            surf.blit(hint, (side_x, MARGIN + 310))

        # Log
        y = MARGIN + 380
        for line in self.log:
            surf.blit(self.font.render(line, True, DARK), (side_x, y))
            y += 20


class GameOverScreen:
    def __init__(self, app, winner, mode):
        self.app = app
        self.font = pygame.font.SysFont("Arial", 26, bold=True)
        self.winner = winner
        self.mode = mode
        self.buttons = [Button((WIN_W // 2 - 90, WIN_H - 100, 180, 50),
                               "New Game", self.new_game, self.font)]

    def new_game(self):
        self.app.flash = None
        self.app.screen = SetupScreen(self.app)

    def draw(self, surf):
        surf.fill((250, 250, 250))
        t = self.font.render(f"{NAMES[self.winner]} ({self.mode}) WINS!", True, COLORS[self.winner])
        surf.blit(t, t.get_rect(center=(WIN_W // 2, WIN_H // 2 - 40)))
        for b in self.buttons:
            b.draw(surf)

    def handle(self, event):
        for b in self.buttons:
            b.handle(event)

    def update(self):
        pass


class LudoApp:
    """Pygame app shell with three screens: Setup -> Play -> GameOver."""

    def __init__(self):
        pygame.init()
        self.screen_surf = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Ludo AI - Expectimax (OOP + Pygame + NumPy)")
        self.clock = pygame.time.Clock()
        self.flash = None
        self.screen = SetupScreen(self)
        self.running = True

    def start_game(self, modes, depth):
        self.flash = None
        self.screen = PlayScreen(self, modes, depth)

    def game_over(self, winner, mode):
        self.screen = GameOverScreen(self, winner, mode)

    def run(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.screen.handle(event)
            self.screen.update()
            self.screen.draw(self.screen_surf)
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


def run_gui():
    sys.modules.setdefault("ludo", sys.modules[__name__])
    from tkinter_ui import run_gui as run_tkinter_gui

    run_tkinter_gui()


# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", type=int, default=0,
                    help="run N headless games instead of the GUI")
    ap.add_argument("--depth", type=int, default=1,
                    help="Expectimax depth for simulation")
    ap.add_argument("--types", nargs="+",
                    default=["Aggressive", "Defensive", "Expectimax", "Random"],
                    choices=AI_TYPES)
    a = ap.parse_args()

    if a.sim:
        simulate(a.types, a.sim, a.depth)
    else:
        run_gui()