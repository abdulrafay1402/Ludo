"""Tkinter interface for the Ludo AI game engine."""
import json
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ludo import (
    COLORS,
    DIRS,
    FINISH,
    HOME_COL,
    LIGHT,
    NAMES,
    QUAD,
    SAFE,
    START,
    TRACK,
    YARD,
    YARD_CELLS,
    LudoGame,
    token_cell,
)


BACKGROUND = "#F3F5F8"
CARD = "#FFFFFF"
TEXT = "#172033"
SECONDARY_TEXT = "#667085"
MUTED_TEXT = "#98A2B3"
PRIMARY = "#8A5A2B"
PRIMARY_HOVER = "#6E4520"
PRIMARY_LIGHT = "#F1E4D3"
SURFACE_LOW = "#F1F4F9"
SURFACE_HIGH = "#E4EAF2"
BORDER = "#DCE2EA"
BOARD_FELT = "#23634F"
BOARD_FELT_DARK = "#164B3B"
BOARD_FRAME = "#253449"
TRACK_TILE = "#FFFDF8"
PLAYER_HEX = ("#E64B4B", "#27A875", "#E7AA32", "#4388D3")
PLAYER_TINT = ("#FCE7E7", "#E2F4EC", "#FBF0D7", "#E7F0FB")
PLAYER_DARK = ("#B8323D", "#14734F", "#986513", "#285A99")
PLAYER_SHADOW = ("#852B36", "#10563E", "#775014", "#204875")
DEPTH_LABELS = (
    "Instant heuristic",
    "Fast search",
    "Balanced search",
    "Deep search",
)
MODE_NAMES = ("Human", "Expectimax", "Aggressive", "Defensive", "Random")
MODE_DEFAULTS = {1: "Expectimax", 2: "Aggressive", 3: "Defensive"}


def _hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _make_button(parent, text, command, primary=False, width=None):
    background = PRIMARY if primary else CARD
    foreground = "#FFFFFF" if primary else TEXT
    return tk.Button(
        parent,
        text=text,
        command=command,
        width=width,
        bg=background,
        fg=foreground,
        activebackground=PRIMARY_HOVER if primary else SURFACE_LOW,
        activeforeground="#FFFFFF" if primary else TEXT,
        disabledforeground=MUTED_TEXT,
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=PRIMARY if primary else BORDER,
        highlightcolor=PRIMARY,
        padx=14,
        pady=9,
        cursor="hand2",
        font=("Segoe UI Semibold", 10),
    )


class LudoTkApp:
    """Application shell and navigation for the three game screens."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Ludo AI - Match Arena")
        self.root.geometry("1440x900")
        self.root.minsize(1024, 700)
        self.root.configure(bg=BACKGROUND)

        self.setup_count = 4
        self.setup_modes = {
            0: "Human",
            1: "Expectimax",
            2: "Aggressive",
            3: "Defensive",
        }
        self.setup_depth = 2
        self.current_modes = dict(self.setup_modes)
        self.current_depth = self.setup_depth
        self.game = None
        self.play_screen = None
        self.setup_screen = None
        self.result_screen = None
        self.result_data = None
        self.active_screen = "setup"

        self._configure_styles()
        self._build_shell()
        self.show_setup()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _configure_styles(self):
        style = ttk.Style(self.root)
        style.configure(
            "Ludo.TCombobox",
            padding=8,
            fieldbackground=CARD,
            background=CARD,
            foreground=TEXT,
        )
        for player, color in enumerate(PLAYER_HEX):
            style.configure(
                f"Ludo{player}.Horizontal.TProgressbar",
                troughcolor=SURFACE_HIGH,
                background=color,
                thickness=9,
            )

    def _build_shell(self):
        header = tk.Frame(self.root, bg=CARD, height=62, highlightbackground=BORDER, highlightthickness=1)
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=CARD)
        brand.pack(side="left", padx=(24, 18))
        tk.Label(
            brand,
            text="Ludo AI",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 17),
        ).pack(side="left")
        tk.Label(
            brand,
            text="  v1.4  TKINTER",
            bg=SURFACE_HIGH,
            fg=SECONDARY_TEXT,
            padx=8,
            pady=3,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(8, 0))

        nav = tk.Frame(header, bg=BACKGROUND, padx=4, pady=4)
        nav.pack(side="left", padx=12)
        self.nav_buttons = {}
        for key, label in (
            ("setup", "Setup Match"),
            ("play", "Play Board"),
            ("result", "Game Over"),
        ):
            button = tk.Button(
                nav,
                text=label,
                command=lambda screen=key: self.navigate(screen),
                relief="flat",
                bd=0,
                padx=12,
                pady=7,
                bg=BACKGROUND,
                fg=SECONDARY_TEXT,
                activebackground=CARD,
                activeforeground=TEXT,
                font=("Segoe UI", 9, "bold"),
                cursor="hand2",
            )
            button.pack(side="left", padx=2)
            self.nav_buttons[key] = button

        header_right = tk.Frame(header, bg=CARD)
        header_right.pack(side="right", padx=22)
        tk.Label(
            header_right,
            text="AL-2002  ·  AI LAB",
            bg=SURFACE_LOW,
            fg=SECONDARY_TEXT,
            padx=9,
            pady=6,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 10))
        self.pause_button = _make_button(header_right, "Pause", self.toggle_pause)
        self.pause_button.pack(side="left", padx=(0, 8))
        _make_button(header_right, "New Game", self.show_setup, primary=True).pack(side="left")

        self.content = tk.Frame(self.root, bg=BACKGROUND)
        self.content.pack(fill="both", expand=True)

        footer = tk.Frame(self.root, bg=CARD, height=35, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text="Ludo AI Engine  ·  Deterministic RNG Core  ·  Expectimax Search",
            bg=CARD,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=24, pady=8)
        tk.Label(
            footer,
            text="Match Arena  ·  Tkinter",
            bg=CARD,
            fg=MUTED_TEXT,
            font=("Segoe UI", 8),
        ).pack(side="right", padx=24, pady=8)

    def _set_navigation(self):
        for key, button in self.nav_buttons.items():
            enabled = (
                key == "setup"
                or (key == "play" and self.play_screen is not None and self.active_screen != "result")
                or (key == "result" and self.result_data is not None)
            )
            button.configure(
                state="normal" if enabled else "disabled",
                bg=PRIMARY if key == self.active_screen else BACKGROUND,
                fg="#FFFFFF" if key == self.active_screen else SECONDARY_TEXT,
            )
        self.pause_button.configure(
            state="normal" if self.active_screen == "play" else "disabled",
            text=(
                "Resume"
                if self.play_screen is not None and self.play_screen.paused
                else "Pause"
            ),
        )

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def navigate(self, screen):
        if screen == "setup":
            self.show_setup()
        elif screen == "play" and self.play_screen is not None:
            self.show_play()
        elif screen == "result" and self.result_data is not None:
            self.show_result()

    def show_setup(self):
        if self.play_screen is not None:
            self.play_screen.dispose()
            self.play_screen = None
        self.result_data = None
        self.result_screen = None
        self.active_screen = "setup"
        self._clear_content()
        self.setup_screen = SetupScreen(self, self.content)
        self._set_navigation()

    def start_game(self, modes, depth):
        self.current_modes = dict(modes)
        self.current_depth = depth
        self.setup_modes.update(modes)
        self.setup_count = len(modes)
        self.setup_depth = depth
        if self.play_screen is not None:
            self.play_screen.dispose()
        self.result_data = None
        self.result_screen = None
        self.active_screen = "play"
        self._clear_content()
        self.play_screen = PlayScreen(self, self.content, modes, depth)
        self._set_navigation()
        self.play_screen.start()

    def show_play(self):
        if self.play_screen is None:
            return
        if self.active_screen == "play":
            return
        self.active_screen = "play"
        self._clear_content()
        self.play_screen.build(self.content)
        self._set_navigation()
        self.play_screen.refresh()

    def show_result(self):
        if self.result_data is None:
            return
        if self.active_screen == "result":
            return
        self.active_screen = "result"
        self._clear_content()
        self.result_screen = GameOverScreen(self, self.content, self.result_data)
        self._set_navigation()

    def game_over(self, winner, mode):
        if self.play_screen is None:
            return
        self.result_data = self.play_screen.get_result(winner, mode)
        self.active_screen = "result"
        self._clear_content()
        self.result_screen = GameOverScreen(self, self.content, self.result_data)
        self._set_navigation()

    def toggle_pause(self):
        if self.active_screen == "play" and self.play_screen is not None:
            self.play_screen.toggle_pause()

    def close(self):
        if self.play_screen is not None:
            self.play_screen.dispose()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


class SetupScreen:
    """Match options, seat assignments, depth selection, and launch action."""

    def __init__(self, app, parent):
        self.app = app
        self.parent = parent
        self.mode_vars = {}
        self.seat_rows = {}
        self.seat_details = {}
        self.count_buttons = {}
        self.depth_value = tk.IntVar(value=app.setup_depth)
        self.depth_badge = None

        outer = tk.Frame(parent, bg=BACKGROUND, padx=28, pady=18)
        outer.pack(fill="both", expand=True)
        title_row = tk.Frame(outer, bg=BACKGROUND)
        title_row.pack(fill="x", pady=(0, 14))
        title_block = tk.Frame(title_row, bg=BACKGROUND)
        title_block.pack(side="left")
        tk.Label(
            title_block,
            text="Set up your match",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Segoe UI Semibold", 25),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="Pick the number of players and assign an AI brain to each seat.",
            bg=BACKGROUND,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(3, 0))
        tk.Label(
            title_row,
            text="TOURNAMENT ENGINE  ·  ENGINE v1.4",
            bg=PRIMARY_LIGHT,
            fg=PRIMARY,
            padx=12,
            pady=7,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right", anchor="s")

        card = tk.Frame(outer, bg=CARD, padx=24, pady=18, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True)
        card.grid_columnconfigure(0, weight=1)

        player_heading = tk.Frame(card, bg=CARD)
        player_heading.grid(row=0, column=0, sticky="ew")
        self._section_label(player_heading, "PLAYERS")
        counts = tk.Frame(card, bg=CARD)
        counts.grid(row=1, column=0, sticky="ew", pady=(7, 14))
        for count in (2, 3, 4):
            button = _make_button(
                counts,
                f"{count} Players",
                lambda value=count: self.set_count(value),
                width=16,
            )
            button.pack(side="left", padx=(0, 8))
            self.count_buttons[count] = button

        seat_heading = tk.Frame(card, bg=CARD)
        seat_heading.grid(row=2, column=0, sticky="ew", pady=(2, 6))
        self._section_label(seat_heading, "SEAT ASSIGNMENTS & ENGINE BRAINS")
        tk.Label(
            seat_heading,
            text="Choose Human or an AI strategy for each active seat.",
            bg=CARD,
            fg=MUTED_TEXT,
            font=("Segoe UI", 8),
        ).pack(side="right")

        seats = tk.Frame(card, bg=CARD)
        seats.grid(row=3, column=0, sticky="ew")
        seats.grid_columnconfigure(1, weight=1)
        positions = ("[0, 4]", "[4, 14]", "[14, 10]", "[10, 0]")
        for player in range(4):
            row = tk.Frame(seats, bg="#F8FAFF", padx=12, pady=7)
            row.grid(row=player, column=0, sticky="ew", pady=3)
            row.grid_columnconfigure(1, weight=1)
            tk.Label(
                row,
                text="●",
                bg="#F8FAFF",
                fg=PLAYER_HEX[player],
                font=("Segoe UI", 15, "bold"),
            ).grid(row=0, column=0, rowspan=2, padx=(0, 10))
            tk.Label(
                row,
                text=f"{NAMES[player]} Base  ·  P{player + 1}",
                bg="#F8FAFF",
                fg=PLAYER_DARK[player],
                font=("Segoe UI Semibold", 10),
            ).grid(row=0, column=1, sticky="w")
            details = tk.Label(
                row,
                text=f"Position {positions[player]}",
                bg="#F8FAFF",
                fg=SECONDARY_TEXT,
                font=("Segoe UI", 8),
            )
            details.grid(row=1, column=1, sticky="w")
            self.seat_details[player] = details
            variable = tk.StringVar(value=self.app.setup_modes.get(player, "None"))
            combo = ttk.Combobox(
                row,
                textvariable=variable,
                values=MODE_NAMES,
                state="readonly",
                style="Ludo.TCombobox",
                width=24,
            )
            combo.grid(row=0, column=2, rowspan=2, sticky="e", padx=(12, 2))
            combo.bind(
                "<<ComboboxSelected>>",
                lambda _event, seat=player: self._mode_changed(seat),
            )
            self.mode_vars[player] = variable
            self.seat_rows[player] = (row, combo)

        depth_frame = tk.Frame(card, bg=SURFACE_LOW, padx=14, pady=10)
        depth_frame.grid(row=4, column=0, sticky="ew", pady=(10, 8))
        depth_frame.grid_columnconfigure(0, weight=1)
        depth_header = tk.Frame(depth_frame, bg=SURFACE_LOW)
        depth_header.grid(row=0, column=0, sticky="ew")
        self._section_label(depth_header, "LOOK-AHEAD DEPTH")
        self.depth_badge = tk.Label(
            depth_header,
            bg=PRIMARY_LIGHT,
            fg=PRIMARY,
            padx=8,
            pady=4,
            font=("Segoe UI", 8, "bold"),
        )
        self.depth_badge.pack(side="right")
        tk.Scale(
            depth_frame,
            from_=0,
            to=3,
            orient="horizontal",
            variable=self.depth_value,
            command=self._depth_changed,
            showvalue=False,
            resolution=1,
            bg=SURFACE_LOW,
            fg=TEXT,
            troughcolor="#D7D4EA",
            activebackground=PRIMARY,
            highlightthickness=0,
            bd=0,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 2))
        depth_labels = tk.Frame(depth_frame, bg=SURFACE_LOW)
        depth_labels.grid(row=2, column=0, sticky="ew")
        for depth, label in enumerate(("d = 0 · Instant", "d = 1 · Fast", "d = 2 · Balanced", "d = 3 · Deep")):
            tk.Label(
                depth_labels,
                text=label,
                bg=SURFACE_LOW,
                fg=SECONDARY_TEXT,
                font=("Segoe UI", 8),
            ).pack(side="left", expand=True)

        preset_row = tk.Frame(card, bg=CARD)
        preset_row.grid(row=5, column=0, sticky="ew", pady=(4, 8))
        self._section_label(preset_row, "QUICK PRESETS")
        presets = tk.Frame(preset_row, bg=CARD)
        presets.pack(side="right")
        for text, count, depth in (
            ("Classic 4-Player", 4, 1),
            ("1v1 vs Expectimax", 2, 2),
            ("Tournament AI Clash", 4, 3),
        ):
            _make_button(
                presets,
                text,
                lambda n=count, d=depth: self.apply_preset(n, d),
            ).pack(side="left", padx=(5, 0))

        _make_button(
            card,
            "Launch Match Arena  →",
            self.launch,
            primary=True,
        ).grid(row=6, column=0, sticky="ew", pady=(4, 6), ipady=5)
        tk.Label(
            card,
            text="Roll a 6 to leave the yard  ·  Capture, roll six, or reach home for an extra turn",
            bg=CARD,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 8),
        ).grid(row=7, column=0, pady=(3, 0))
        self._update_controls()

    @staticmethod
    def _section_label(parent, text):
        tk.Label(
            parent,
            text=text,
            bg=parent.cget("bg"),
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")

    def set_count(self, count):
        self.app.setup_count = count
        active_seats = self.active_seats(count)
        for player in range(4):
            variable = self.mode_vars[player]
            if player not in active_seats:
                self.app.setup_modes[player] = "None"
                variable.set("None")
            elif variable.get() == "None":
                mode = "Human" if player == 0 else MODE_DEFAULTS.get(player, "Random")
                self.app.setup_modes[player] = mode
                variable.set(mode)
        self._update_controls()

    @staticmethod
    def active_seats(count):
        return (0, 2) if count == 2 else tuple(range(count))

    def _mode_changed(self, player):
        self.app.setup_modes[player] = self.mode_vars[player].get()

    def _depth_changed(self, value):
        self.app.setup_depth = int(float(value))
        self._update_depth_badge()

    def _update_depth_badge(self):
        depth = self.depth_value.get()
        self.depth_badge.configure(
            text=f"Depth {depth}  ·  {DEPTH_LABELS[depth]}"
        )

    def _update_controls(self):
        for count, button in self.count_buttons.items():
            selected = count == self.app.setup_count
            button.configure(
                bg=PRIMARY if selected else CARD,
                fg="#FFFFFF" if selected else TEXT,
                activebackground=PRIMARY_HOVER if selected else SURFACE_LOW,
                activeforeground="#FFFFFF" if selected else TEXT,
                highlightbackground=PRIMARY if selected else BORDER,
            )
        for player, (row, combo) in self.seat_rows.items():
            active = player in self.active_seats(self.app.setup_count)
            diagonal_seat = self.app.setup_count == 2 and player == 2
            combo.configure(
                state="readonly" if active else "disabled",
                values=MODE_NAMES if active else ("None",),
            )
            row.configure(bg="#F8FAFF" if active else "#F2F3F5")
            self.seat_details[player].configure(
                text=(
                    "Position [14, 10]  ·  OPPOSITE CORNER"
                    if diagonal_seat
                    else (
                        f"Position {('[0, 4]', '[4, 14]', '[14, 10]', '[10, 0]')[player]}"
                        if active
                        else "Inactive seat"
                    )
                ),
                fg=PLAYER_DARK[player] if diagonal_seat else SECONDARY_TEXT,
            )
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=row.cget("bg"))
        self._update_depth_badge()

    def apply_preset(self, count, depth):
        self.set_count(count)
        if count == 2:
            self.mode_vars[2].set("Expectimax")
            self.app.setup_modes[2] = "Expectimax"
        self.depth_value.set(depth)
        self._depth_changed(depth)

    def launch(self):
        active_seats = self.active_seats(self.app.setup_count)
        modes = {
            player: self.mode_vars[player].get()
            for player in active_seats
        }
        if len(modes) < 2 or any(mode not in MODE_NAMES for mode in modes.values()):
            messagebox.showerror("Invalid setup", "Choose at least two valid player modes.")
            return
        self.app.start_game(modes, self.depth_value.get())


class PlayScreen:
    """Live board, die input, AI turns, pause, and match telemetry."""

    def __init__(self, app, parent, modes, depth):
        self.app = app
        self.parent = parent
        self.modes = dict(modes)
        self.depth = depth
        self.game = LudoGame(self.modes, depth)
        self.phase = "roll"
        self.dice = 0
        self.moves = []
        self.pending_extra = False
        self.paused = False
        self.auto_ai = tk.BooleanVar(value=True)
        self.after_id = None
        self.scheduled_callback = None
        self.scheduled_delay = 0
        self.roll_count = 0
        self.capture_count = 0
        self.log = []
        self.started_at = time.time()
        self.finished = False
        self._building = False
        self._space_binding = None
        self.build(parent)

    def build(self, parent):
        self.parent = parent
        self._building = True
        outer = tk.Frame(parent, bg=BACKGROUND, padx=18, pady=12)
        outer.pack(fill="both", expand=True)

        status = tk.Frame(outer, bg=CARD, padx=13, pady=8, highlightbackground=BORDER, highlightthickness=1)
        status.pack(fill="x", pady=(0, 10))
        self.status_var = tk.StringVar()
        tk.Label(
            status,
            textvariable=self.status_var,
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        tk.Label(
            status,
            text=f"EXPECTIMAX  ·  DEPTH {self.depth}",
            bg=PRIMARY_LIGHT,
            fg=PRIMARY,
            padx=9,
            pady=4,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")

        workspace = tk.Frame(outer, bg=BACKGROUND)
        workspace.pack(fill="both", expand=True)
        workspace.grid_columnconfigure(0, weight=3, minsize=460)
        workspace.grid_columnconfigure(1, weight=1, minsize=300)
        workspace.grid_rowconfigure(0, weight=1)

        board_card = tk.Frame(workspace, bg=CARD, padx=10, pady=10, highlightbackground=BORDER, highlightthickness=1)
        board_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        board_card.grid_rowconfigure(0, weight=1)
        board_card.grid_columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(
            board_card,
            bg=BOARD_FRAME,
            highlightthickness=0,
            width=680,
            height=680,
            cursor="crosshair",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self._draw_board)

        side = tk.Frame(workspace, bg=BACKGROUND, width=330)
        side.grid(row=0, column=1, sticky="nsew")
        side.grid_propagate(False)
        self._build_turn_card(side)
        self._build_dice_card(side)
        self._build_progress_card(side)
        self._build_log_card(side)

        footer = tk.Frame(outer, bg=BACKGROUND)
        footer.pack(fill="x", pady=(7, 0))
        tk.Label(
            footer,
            text="Click a highlighted token to move it",
            bg=BACKGROUND,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 8),
        ).pack(side="left")
        tk.Label(
            footer,
            text=f"{len(self.game.active)} PLAYERS  ·  15 × 15 MATRIX",
            bg=BACKGROUND,
            fg=MUTED_TEXT,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")
        self._space_binding = self.app.root.bind("<space>", self._space_pressed)
        self._building = False
        self.refresh()

    def _card(self, parent, padding=12):
        return tk.Frame(
            parent,
            bg=CARD,
            padx=padding,
            pady=padding,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

    def _build_turn_card(self, parent):
        card = self._card(parent, 11)
        card.pack(fill="x", pady=(0, 8))
        self.turn_title = tk.Label(
            card,
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 12),
        )
        self.turn_title.pack(anchor="w")
        self.turn_subtitle = tk.Label(
            card,
            bg=CARD,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 9),
        )
        self.turn_subtitle.pack(anchor="w", pady=(2, 7))
        self.hint_var = tk.StringVar()
        tk.Label(
            card,
            textvariable=self.hint_var,
            bg=PLAYER_TINT[0],
            fg=TEXT,
            justify="left",
            wraplength=280,
            padx=8,
            pady=7,
            font=("Segoe UI", 8),
        ).pack(fill="x")

    def _build_dice_card(self, parent):
        card = self._card(parent, 11)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(
            card,
            text="ACTIVE DICE VALUE",
            bg=CARD,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", pady=(8, 5))
        self.die_canvas = tk.Canvas(
            row,
            width=68,
            height=68,
            bg=CARD,
            highlightthickness=0,
        )
        self.die_canvas.pack(side="left")
        action = tk.Frame(row, bg=CARD)
        action.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.roll_button = _make_button(
            action,
            "Roll Dice  (Space)",
            self.roll,
            primary=True,
        )
        self.roll_button.pack(fill="x")
        self.step_button = _make_button(action, "Run AI Turn", self.step_ai)
        self.step_button.pack(fill="x", pady=(5, 0))

        self.auto_check = tk.Checkbutton(
            card,
            text="Automate AI turns",
            variable=self.auto_ai,
            command=self._auto_setting_changed,
            bg=CARD,
            fg=SECONDARY_TEXT,
            activebackground=CARD,
            activeforeground=TEXT,
            selectcolor=CARD,
            font=("Segoe UI", 8),
        )
        self.auto_check.pack(anchor="w", pady=(2, 0))
        controls = tk.Frame(card, bg=CARD)
        controls.pack(fill="x", pady=(8, 0))
        self.pause_local_button = _make_button(
            controls,
            "Pause",
            self.toggle_pause,
        )
        self.pause_local_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        _make_button(
            controls,
            "New Setup",
            self.app.show_setup,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _build_progress_card(self, parent):
        card = self._card(parent, 11)
        card.pack(fill="x", pady=(0, 8))
        heading = tk.Frame(card, bg=CARD)
        heading.pack(fill="x", pady=(0, 5))
        tk.Label(
            heading,
            text="RACE PROGRESS",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        tk.Label(
            heading,
            text="TOKENS HOME",
            bg=CARD,
            fg=MUTED_TEXT,
            font=("Segoe UI", 7, "bold"),
        ).pack(side="right")

        self.progress_labels = {}
        self.progress_bars = {}
        for player in self.game.active:
            line = tk.Frame(card, bg=CARD)
            line.pack(fill="x", pady=3)
            name = tk.Label(
                line,
                text=NAMES[player],
                bg=CARD,
                fg=PLAYER_DARK[player],
                width=8,
                anchor="w",
                font=("Segoe UI", 8, "bold"),
            )
            name.pack(side="left")
            bar = ttk.Progressbar(
                line,
                maximum=FINISH * 4,
                style=f"Ludo{player}.Horizontal.TProgressbar",
            )
            bar.pack(side="left", fill="x", expand=True, padx=5)
            home = tk.Label(
                line,
                bg=CARD,
                fg=SECONDARY_TEXT,
                width=5,
                anchor="e",
                font=("Segoe UI", 8),
            )
            home.pack(side="right")
            self.progress_bars[player] = bar
            self.progress_labels[player] = home

    def _build_log_card(self, parent):
        card = self._card(parent, 10)
        card.pack(fill="both", expand=True)
        heading = tk.Frame(card, bg=CARD)
        heading.pack(fill="x", pady=(0, 4))
        tk.Label(
            heading,
            text="MATCH LOG",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI Semibold", 9),
        ).pack(side="left")
        tk.Label(
            heading,
            text="AUTO-SCROLL",
            bg=CARD,
            fg=SECONDARY_TEXT,
            font=("Segoe UI", 7, "bold"),
        ).pack(side="right")
        self.log_text = tk.Text(
            card,
            height=9,
            wrap="word",
            bd=0,
            bg=CARD,
            fg=TEXT,
            font=("Consolas", 8),
            state="disabled",
        )
        self.log_text.pack(fill="both", expand=True)

    def start(self):
        self.app.game = self.game
        self._begin_turn()

    def _begin_turn(self):
        if self.finished:
            return
        self.moves = []
        self.dice = 0
        self.pending_extra = False
        player = self.game.turn
        if self.game.players[player].is_human:
            self.phase = "roll"
        elif self.auto_ai.get():
            self.phase = "busy"
            self._schedule(self._roll_and_branch, 480)
        else:
            self.phase = "ai_ready"
        self.refresh()

    def _schedule(self, callback, delay):
        self._cancel_timer()
        self.scheduled_callback = callback
        self.scheduled_delay = delay
        if not self.paused:
            self.after_id = self.app.root.after(delay, self._run_scheduled)

    def _run_scheduled(self):
        self.after_id = None
        if self.paused:
            return
        callback = self.scheduled_callback
        self.scheduled_callback = None
        if callback is not None and not self.finished:
            callback()

    def _cancel_timer(self):
        if self.after_id is not None:
            try:
                self.app.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None

    def _space_pressed(self, _event):
        if self.phase == "roll" and not self.paused:
            self.roll()
        return "break"

    def roll(self):
        if self.paused or self.phase != "roll":
            return
        self.phase = "busy"
        self._roll_and_branch()

    def _roll_and_branch(self):
        if self.paused or self.finished:
            return
        self.dice = self.game.roll()
        self.roll_count += 1
        player = self.game.turn
        self.moves = self.game.legal(self.dice)
        self._add_log(f"{NAMES[player]} rolled {self.dice}.")
        if not self.moves:
            self._add_log(f"{NAMES[player]} has no legal move.")
            self.phase = "busy"
            self._schedule(self._advance_turn, 650)
        elif len(self.moves) == 1:
            self._do_move(self.moves[0])
        elif self.game.players[player].is_human:
            self.phase = "pick"
            self._add_log("Choose one of the highlighted tokens.")
        else:
            self.phase = "busy"
            self._schedule(self._ai_step, 360)
        self.refresh()

    def _ai_step(self):
        if self.paused or self.finished or not self.moves:
            return
        token = self.game.ai_choose(self.dice)
        if token is None:
            token = self.moves[0]
        self._do_move(token)

    def step_ai(self):
        if self.paused or self.phase != "ai_ready":
            return
        self.phase = "busy"
        self._roll_and_branch()

    def _do_move(self, token):
        player = self.game.turn
        before = int(self.game.state[player, token])
        extra, captured = self.game.apply(token, self.dice)
        after = int(self.game.state[player, token])
        self.capture_count += captured
        if before == YARD:
            action = "left the yard"
        elif after == FINISH:
            action = "reached home"
        else:
            action = f"moved to step {after}"
        detail = f"{NAMES[player]} moved token {token + 1}: {action}."
        if captured:
            detail += f" Captured {captured} token{'s' if captured != 1 else ''}."
        self._add_log(detail)
        self.moves = []
        winner = self.game.winner()
        if winner is not None:
            self.finished = True
            self.phase = "over"
            self.refresh()
            self.app.game_over(winner, self.game.modes[winner])
            return
        self.pending_extra = extra
        self.phase = "busy"
        if extra:
            self._add_log(f"{NAMES[player]} earned an extra turn.")
        self._schedule(self._advance_turn, 480)
        self.refresh()

    def _advance_turn(self):
        if not self.pending_extra:
            self.game.advance(False)
        self._begin_turn()

    def _add_log(self, message):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "player": NAMES[self.game.turn],
            "message": message,
        }
        self.log.append(entry)
        if hasattr(self, "log_text"):
            self._refresh_log()

    def _refresh_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        for entry in self.log[-9:]:
            self.log_text.insert(
                "end",
                f"[{entry['time']}] {entry['message']}\n",
            )
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _draw_die(self):
        if not hasattr(self, "die_canvas"):
            return
        canvas = self.die_canvas
        canvas.delete("all")
        canvas.create_rectangle(
            6, 5, 62, 61,
            fill="#FFFFFF",
            outline=BORDER,
            width=2,
        )
        if not self.dice:
            canvas.create_text(
                34, 33, text="–", fill=MUTED_TEXT,
                font=("Segoe UI", 20, "bold"),
            )
            return
        positions = {
            1: ((34, 33),),
            2: ((20, 19), (48, 47)),
            3: ((20, 19), (34, 33), (48, 47)),
            4: ((20, 19), (48, 19), (20, 47), (48, 47)),
            5: ((20, 19), (48, 19), (34, 33), (20, 47), (48, 47)),
            6: ((20, 17), (48, 17), (20, 33), (48, 33), (20, 49), (48, 49)),
        }
        for x, y in positions[self.dice]:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=PRIMARY, outline="")

    def _refresh_progress(self):
        for player in self.game.active:
            row = self.game.state[player]
            self.progress_bars[player]["value"] = sum(
                max(0, int(step)) for step in row
            )
            homes = sum(int(step) == FINISH for step in row)
            self.progress_labels[player].configure(text=f"{homes}/4")

    def _cell_center(self, row, col, origin_x, origin_y, cell):
        return (
            origin_x + (col + 0.5) * cell,
            origin_y + (row + 0.5) * cell,
        )

    def _draw_board(self, _event=None):
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 80 or height < 80:
            return
        canvas.delete("all")
        board_size = min(width, height) - 24
        cell = board_size / 15
        origin_x = (width - board_size) / 2
        origin_y = (height - board_size) / 2
        canvas.create_rectangle(
            origin_x - 7,
            origin_y - 7,
            origin_x + board_size + 7,
            origin_y + board_size + 7,
            fill=BOARD_FRAME,
            outline="#172234",
            width=2,
        )
        canvas.create_rectangle(
            origin_x,
            origin_y,
            origin_x + board_size,
            origin_y + board_size,
            fill=BOARD_FELT,
            outline="#B7C5BD",
            width=2,
        )

        for player, (row, col) in enumerate(QUAD):
            x0, y0 = origin_x + col * cell, origin_y + row * cell
            canvas.create_rectangle(
                x0, y0, x0 + 6 * cell, y0 + 6 * cell,
                fill=_hex(LIGHT[player]) if player in self.game.active else "#D8DEDA",
                outline="#FFFFFF",
                width=2,
            )
            yard_x0, yard_y0 = x0 + cell * 0.8, y0 + cell * 0.8
            yard_x1, yard_y1 = x0 + cell * 5.2, y0 + cell * 5.2
            canvas.create_rectangle(
                yard_x0, yard_y0, yard_x1, yard_y1,
                fill=CARD,
                outline=_hex(COLORS[player]),
                width=3,
            )
            canvas.create_text(
                x0 + cell * 3,
                y0 + cell * 0.42,
                text=f"{NAMES[player].upper()} HOME",
                fill=PLAYER_DARK[player],
                font=("Segoe UI Semibold", max(7, int(cell * 0.23))),
            )
            for inset in (0.92, 1.04):
                canvas.create_rectangle(
                    x0 + cell * inset,
                    y0 + cell * inset,
                    x0 + 6 * cell - cell * inset,
                    y0 + 6 * cell - cell * inset,
                    outline=PLAYER_TINT[player],
                    width=1,
                )

        for track_index, (row, col) in enumerate(TRACK):
            player = next(
                (index for index, start in enumerate(START) if int(start) == track_index),
                None,
            )
            x0, y0 = origin_x + col * cell, origin_y + row * cell
            canvas.create_rectangle(
                x0 + 1,
                y0 + 2,
                x0 + cell - 1,
                y0 + cell,
                fill="#133F34",
                outline="",
            )
            fill = PLAYER_HEX[player] if player is not None else TRACK_TILE
            canvas.create_rectangle(
                x0 + 1, y0 + 1, x0 + cell - 1, y0 + cell - 2,
                fill=fill,
                outline="#C9D4CF",
                width=1,
            )
            if track_index in SAFE and track_index not in START:
                canvas.create_oval(
                    x0 + cell * 0.23,
                    y0 + cell * 0.23,
                    x0 + cell * 0.77,
                    y0 + cell * 0.77,
                    fill="#F8E7B4",
                    outline="#D7AE53",
                    width=1,
                )
                canvas.create_text(
                    x0 + cell / 2, y0 + cell / 2,
                    text="★",
                    fill="#986513",
                    font=("Segoe UI", max(8, int(cell * 0.38)), "bold"),
                )

        for player, path in enumerate(HOME_COL):
            for row, col in path:
                x0, y0 = origin_x + col * cell, origin_y + row * cell
                canvas.create_rectangle(
                    x0 + 1, y0 + 1, x0 + cell - 1, y0 + cell - 1,
                    fill=PLAYER_TINT[player],
                    outline=PLAYER_HEX[player],
                    width=1,
                )

        center_x, center_y = origin_x + 7.5 * cell, origin_y + 7.5 * cell
        center_points = (
            (origin_x + 6 * cell, origin_y + 6 * cell),
            (origin_x + 9 * cell, origin_y + 9 * cell),
        )
        cx0, cy0 = center_points[0]
        cx1, cy1 = center_points[1]
        canvas.create_polygon(cx0, cy0, center_x, center_y, cx0, cy1, fill=PLAYER_HEX[0], outline="#FFFFFF", width=1)
        canvas.create_polygon(cx0, cy0, center_x, center_y, cx1, cy0, fill=PLAYER_HEX[1], outline="#FFFFFF", width=1)
        canvas.create_polygon(cx1, cy0, center_x, center_y, cx1, cy1, fill=PLAYER_HEX[2], outline="#FFFFFF", width=1)
        canvas.create_polygon(cx0, cy1, center_x, center_y, cx1, cy1, fill=PLAYER_HEX[3], outline="#FFFFFF", width=1)
        canvas.create_oval(
            center_x - cell * 0.38, center_y - cell * 0.38,
            center_x + cell * 0.38, center_y + cell * 0.38,
            fill=CARD,
            outline="#D6DCE4",
            width=2,
        )
        canvas.create_text(
            center_x, center_y,
            text="🏆",
            font=("Segoe UI Emoji", max(10, int(cell * 0.38))),
        )

        for player in range(4):
            for token, (row, col) in enumerate(YARD_CELLS[player]):
                x, y = self._cell_center(row, col, origin_x, origin_y, cell)
                canvas.create_oval(
                    x - cell * 0.32, y - cell * 0.32,
                    x + cell * 0.32, y + cell * 0.32,
                    fill=PLAYER_TINT[player],
                    outline="#D9E0E8",
                    width=2,
                )

        stacks = {}
        for player in self.game.active:
            for token in range(4):
                rel = int(self.game.state[player, token])
                row, col = token_cell(player, rel, token)
                x, y = self._cell_center(row, col, origin_x, origin_y, cell)
                if rel == FINISH:
                    dx, dy = DIRS[player]
                    x = center_x + dx * cell * 0.55 + (token % 2) * cell * 0.22
                    y = center_y + dy * cell * 0.55 + (token // 2) * cell * 0.22
                elif rel != YARD:
                    stack = stacks.get((row, col), 0)
                    stacks[(row, col)] = stack + 1
                    x += (stack % 2) * cell * 0.2 - cell * 0.1
                    y += (stack // 2) * cell * 0.2 - cell * 0.1
                radius = cell * (0.29 if rel == YARD else 0.32)
                selectable = self.phase == "pick" and player == self.game.turn and token in self.moves
                tag = f"token-{player}-{token}"
                canvas.create_oval(
                    x - radius + 1,
                    y - radius + 3,
                    x + radius + 1,
                    y + radius + 3,
                    fill=PLAYER_SHADOW[player],
                    outline="",
                    tags=(tag, "token"),
                )
                canvas.create_oval(
                    x - radius - (3 if selectable else 0),
                    y - radius - (3 if selectable else 0),
                    x + radius + (3 if selectable else 0),
                    y + radius + (3 if selectable else 0),
                    fill=PLAYER_HEX[player],
                    outline=PRIMARY if selectable else PLAYER_DARK[player],
                    width=3 if selectable else 2,
                    tags=(tag, "token"),
                )
                canvas.create_oval(
                    x - radius * 0.57,
                    y - radius * 0.64,
                    x - radius * 0.08,
                    y - radius * 0.16,
                    fill="#FCE9E5",
                    outline="",
                    tags=(tag, "token"),
                )
                if radius > 9:
                    canvas.create_text(
                        x, y, text=str(token + 1), fill="#FFFFFF",
                        font=("Segoe UI", max(7, int(cell * 0.22)), "bold"),
                        tags=(tag, "token"),
                    )
                if selectable:
                    canvas.tag_bind(
                        tag,
                        "<Button-1>",
                        lambda _event, p=player, t=token: self._choose_token(p, t),
                    )

    def _choose_token(self, player, token):
        if self.paused or self.phase != "pick" or player != self.game.turn:
            return
        if token in self.moves:
            self._do_move(token)

    def _auto_setting_changed(self):
        if self.finished:
            return
        player = self.game.turn
        if self.game.players[player].is_human:
            self.refresh()
            return
        if not self.auto_ai.get():
            if self.phase == "busy" and self.scheduled_callback == self._roll_and_branch:
                self._cancel_timer()
                self.scheduled_callback = None
                self.phase = "ai_ready"
        elif self.phase == "ai_ready":
            self.phase = "busy"
            self._schedule(self._roll_and_branch, 260)
        self.refresh()

    def toggle_pause(self):
        if self.finished:
            return
        self.paused = not self.paused
        if self.paused:
            if self.after_id is not None:
                self._cancel_timer()
        elif self.scheduled_callback is not None:
            self.after_id = self.app.root.after(
                self.scheduled_delay,
                self._run_scheduled,
            )
        self.pause_local_button.configure(text="Resume" if self.paused else "Pause")
        self.app._set_navigation()
        self.refresh()

    def refresh(self):
        if self._building or not hasattr(self, "status_var"):
            return
        player = self.game.turn
        mode = self.game.modes[player]
        self.status_var.set(
            f"●  {NAMES[player]}  ·  {mode}     |     ROLLS {self.roll_count:02d}     |     TURN ACTIVE"
        )
        self.turn_title.configure(
            text=f"{NAMES[player]}'s Turn",
            fg=PLAYER_DARK[player],
        )
        self.turn_subtitle.configure(
            text="Human Commander" if mode == "Human" else f"{mode} AI"
        )
        if self.phase == "roll":
            hint = "Roll the die. A highlighted token can be moved after the roll."
        elif self.phase == "pick":
            hint = f"Rolled {self.dice}. Click one of the highlighted {NAMES[player]} tokens."
        elif self.phase == "ai_ready":
            hint = "Run AI Turn to roll and let this seat choose its move."
        elif self.phase == "over":
            hint = "The winner has brought all four tokens home."
        elif self.paused:
            hint = "Resume the match to continue."
        else:
            hint = "The AI is choosing its move."
        self.hint_var.set(hint)
        self.roll_button.configure(
            state="normal" if self.phase == "roll" and not self.paused else "disabled"
        )
        self.step_button.configure(
            state="normal" if self.phase == "ai_ready" and not self.paused else "disabled"
        )
        self.auto_check.configure(
            state="disabled" if self.game.players[player].is_human else "normal"
        )
        self.pause_local_button.configure(
            text="Resume" if self.paused else "Pause",
            state="normal" if self.phase != "over" else "disabled",
        )
        self._draw_die()
        self._refresh_progress()
        self._refresh_log()
        self._draw_board()

    def get_result(self, winner, mode):
        return {
            "winner": winner,
            "mode": mode,
            "depth": self.depth,
            "captures": self.capture_count,
            "tokens_home": int((self.game.state[winner] == FINISH).sum()),
            "rolls": self.roll_count,
            "duration_seconds": max(0, int(time.time() - self.started_at)),
            "modes": dict(self.game.modes),
            "state": self.game.state.tolist(),
            "log": list(self.log),
        }

    def dispose(self):
        self.finished = True
        self._cancel_timer()
        if self._space_binding is not None:
            try:
                self.app.root.unbind("<space>", self._space_binding)
            except tk.TclError:
                pass
            self._space_binding = None


class GameOverScreen:
    """Winner summary with replay, setup, and telemetry export actions."""

    def __init__(self, app, parent, result):
        self.app = app
        self.parent = parent
        self.result = result
        winner = result["winner"]
        color = PLAYER_DARK[winner]
        frame = tk.Frame(parent, bg=BACKGROUND, padx=24, pady=18)
        frame.pack(fill="both", expand=True)
        card = tk.Frame(frame, bg=CARD, padx=28, pady=20, highlightbackground=BORDER, highlightthickness=1)
        card.place(relx=0.5, rely=0.48, anchor="center", relwidth=0.72, relheight=0.84)

        tk.Label(
            card,
            text="🏆",
            bg=CARD,
            fg="#E5A914",
            font=("Segoe UI Emoji", 46),
        ).pack(pady=(0, 2))
        tk.Label(
            card,
            text=f"{NAMES[winner]} Wins!",
            bg=CARD,
            fg=color,
            font=("Segoe UI Semibold", 28),
        ).pack()
        tk.Label(
            card,
            text=f"Mode: {result['mode']}    ·    Depth {result['depth']}    ·    {result['rolls']} rolls",
            bg=PRIMARY_LIGHT,
            fg=PRIMARY,
            padx=13,
            pady=6,
            font=("Segoe UI", 9, "bold"),
        ).pack(pady=(8, 14))

        stats = tk.Frame(card, bg=BACKGROUND, padx=8, pady=8)
        stats.pack(fill="x", pady=(0, 12))
        for title, value, value_color in (
            ("CAPTURES", str(result["captures"]), color),
            ("TOKENS HOME", f"{result['tokens_home']} / 4", PLAYER_DARK[winner]),
            ("TOTAL ROLLS", str(result["rolls"]), TEXT),
            ("MATCH TIME", self._format_duration(result["duration_seconds"]), PRIMARY),
        ):
            stat = tk.Frame(stats, bg=CARD, padx=8, pady=9)
            stat.pack(side="left", fill="both", expand=True, padx=3)
            tk.Label(
                stat,
                text=title,
                bg=CARD,
                fg=SECONDARY_TEXT,
                font=("Segoe UI", 7, "bold"),
            ).pack()
            tk.Label(
                stat,
                text=value,
                bg=CARD,
                fg=value_color,
                font=("Segoe UI Semibold", 15),
            ).pack(pady=(3, 0))

        last_move = result["log"][-1]["message"] if result["log"] else "Match finished."
        insight = tk.Frame(card, bg=PLAYER_TINT[winner], padx=12, pady=10)
        insight.pack(fill="x", pady=(0, 14))
        tk.Label(
            insight,
            text="MATCH HIGHLIGHT",
            bg=PLAYER_TINT[winner],
            fg=color,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            insight,
            text=last_move,
            bg=PLAYER_TINT[winner],
            fg=TEXT,
            wraplength=700,
            justify="left",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(3, 0))

        actions = tk.Frame(card, bg=CARD)
        actions.pack(fill="x")
        _make_button(
            actions,
            "↻  Play Again",
            self.play_again,
            primary=True,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=4)
        _make_button(
            actions,
            "New Setup",
            self.app.show_setup,
        ).pack(side="left", fill="x", expand=True, padx=5, ipady=4)
        _make_button(
            actions,
            "Export Match JSON",
            self.export,
        ).pack(side="left", fill="x", expand=True, padx=(5, 0), ipady=4)

    @staticmethod
    def _format_duration(seconds):
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def play_again(self):
        self.app.start_game(
            self.result["modes"],
            self.result["depth"],
        )

    def export(self):
        path = filedialog.asksaveasfilename(
            title="Export match telemetry",
            defaultextension=".json",
            filetypes=(("JSON files", "*.json"),),
            initialfile="ludo-match.json",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(self.result, file, indent=2)
        except OSError as error:
            messagebox.showerror("Export failed", f"Could not save match data:\n{error}")
            return
        messagebox.showinfo("Match exported", f"Telemetry saved to:\n{path}")


def run_gui():
    LudoTkApp().run()
