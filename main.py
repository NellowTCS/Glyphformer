"""
Glyphformer: 2D text-based platformer!
"""

import atexit
import sys
import time
from pycomputersdk import (
    Renderer, get_key, Key,
    setup_raw as setup_terminal, restore as restore_terminal, cleanup,
    is_web,
)
from levels import LEVELS

# Physics
GRAVITY        = 0.08
JUMP_VEL       = -1.6
MOVE_ACCEL     = 0.10
FRICTION_AIR   = 0.98
FRICTION_GROUND= 0.88
MAX_SPEED      = 0.50
PLAYER_W       = 0.8
PLAYER_H       = 1.0
SUB_STEPS      = 4

# Display
TARGET_FPS  = 30
FRAME_TIME  = 1.0 / TARGET_FPS
VIEWPORT_W  = 36
VIEWPORT_H  = 20

# Tiles
TILE_AIR    = "  "
TILE_SOLID  = "▓▓"
TILE_COIN   = "◆◆"
TILE_FLAG   = "⚑⚑"
TILE_SPIKE  = "▲▲"
PLAYER_CHAR = "[]"

MAX_LIVES   = 3

# Feel
COYOTE_TIME  = 0.08   # seconds after leaving ground that jump still works
JUMP_BUFFER  = 0.08   # seconds a jump press is remembered before landing

r = Renderer()


#  Helpers

def solid_at(tiles, col, row, lw, lh):
    if col < 0 or col >= lw or row < 0 or row >= lh:
        return True
    return tiles[row][col] == "#"


def aabb_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


def clear_screen():
    r.clear()
    r.flush()


def drain_keys():
    """Flush all pending keystrokes."""
    while get_key() is not None:
        pass


def wait_key(*accept):
    """Block until one of the accepted keys (lowercase) is pressed."""
    while True:
        k = get_key()
        if k is not None:
            kl = k.lower()
            if not accept or kl in accept:
                return kl
        time.sleep(0.02)


def fmt_time(seconds):
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"


#  Player / Game state

class Player:
    def __init__(self, spawn):
        self.reset(spawn)

    def reset(self, spawn):
        self.x  = float(spawn[0]) + 0.1
        self.y  = float(spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.grounded = False
        self.w = PLAYER_W
        self.h = PLAYER_H
        self.coyote_timer = 0.0
        self.jump_buffer_timer = 0.0


class Game:
    def __init__(self):
        self.level_idx      = 0
        self.level          = None
        self.player         = None
        self.coins_left     = []
        self.coins_collected= 0
        self.total_coins    = 0
        self.camera_x       = 0
        self.won            = False
        self.dead           = False
        self.lives          = MAX_LIVES
        self.elapsed        = 0.0
        self.keys           = {}
        self.w_pressed      = False
        # scores: best time per level index
        self.best_times     = {}

    def load_level(self, idx):
        self.level           = LEVELS[idx]
        self.player          = Player(self.level["spawn"])
        self.coins_left      = list(self.level.get("coins", []))
        self.coins_collected = 0
        self.total_coins     = len(self.coins_left)
        self.camera_x        = 0
        self.won             = False
        self.dead            = False
        self.elapsed         = 0.0

    def poll_key(self, key):
        if key is None:
            return
        k = key.lower()
        if k == "w" or key == Key.UP:
            self.w_pressed = True
        if k in ("a",) or key == Key.LEFT:
            self.keys["a"] = True
        if k in ("d",) or key == Key.RIGHT:
            self.keys["d"] = True
        if k in ("s",) or key == Key.DOWN:
            self.keys["s"] = True

    def clear_frame_keys(self):
        self.keys.clear()

    def tick(self, dt):
        if self.won or self.dead:
            return

        self.elapsed += dt

        accel_x  = 0.0
        if self.keys.get("a"):
            accel_x -= MOVE_ACCEL
        if self.keys.get("d"):
            accel_x += MOVE_ACCEL
        fast_fall = self.keys.get("s", False)

        jump_pressed = self.w_pressed
        self.w_pressed = False
        if jump_pressed:
            self.player.jump_buffer_timer = JUMP_BUFFER

        tiles = self.level["tiles"]
        lw    = self.level["width"]
        lh    = self.level["height"]

        # Update coyote timer
        if self.player.grounded:
            self.player.coyote_timer = COYOTE_TIME
        else:
            self.player.coyote_timer = max(0, self.player.coyote_timer - dt)

        for _ in range(SUB_STEPS):
            self.player.vx += accel_x
            friction = FRICTION_AIR if not self.player.grounded else FRICTION_GROUND
            self.player.vx *= friction
            if abs(self.player.vx) > MAX_SPEED:
                self.player.vx = MAX_SPEED if self.player.vx > 0 else -MAX_SPEED
            if abs(self.player.vx) < 0.0005:
                self.player.vx = 0.0
            self.player.x += self.player.vx / SUB_STEPS
            self._resolve_x(tiles, lw, lh)

            grav = GRAVITY
            if fast_fall and not self.player.grounded:
                grav *= 2.0
            self.player.vy += grav
            if self.player.vy > 15.0:
                self.player.vy = 15.0
            self.player.y += self.player.vy / SUB_STEPS
            self.player.grounded = False
            self._resolve_y(tiles, lw, lh)

            # Coyote time + jump buffer
            if self.player.jump_buffer_timer > 0 and (self.player.grounded or self.player.coyote_timer > 0):
                self.player.vy = JUMP_VEL
                self.player.grounded = False
                self.player.jump_buffer_timer = 0.0
                self.player.coyote_timer = 0.0

        # Decrement jump buffer if it wasn't consumed
        if self.player.jump_buffer_timer > 0:
            self.player.jump_buffer_timer = max(0, self.player.jump_buffer_timer - dt)

        # Fall into pit
        if self.player.y > lh:
            self.dead = True
            return

        # Spike collision
        for sx, sy in self.level.get("spikes", []):
            if aabb_overlap(self.player.x, self.player.y, self.player.w, self.player.h,
                            float(sx), float(sy), 1.0, 1.0):
                self.dead = True
                return

        # Coin pickup
        still_left = []
        for cx, cy in self.coins_left:
            if aabb_overlap(self.player.x, self.player.y, self.player.w, self.player.h,
                            float(cx), float(cy), 1.0, 1.0):
                self.coins_collected += 1
            else:
                still_left.append((cx, cy))
        self.coins_left = still_left

        # Flag
        fx, fy = self.level["flag"]
        if aabb_overlap(self.player.x, self.player.y, self.player.w, self.player.h,
                        float(fx), float(fy), 1.0, 1.0):
            self.won = True
            prev = self.best_times.get(self.level_idx)
            if prev is None or self.elapsed < prev:
                self.best_times[self.level_idx] = self.elapsed

    def _resolve_x(self, tiles, lw, lh):
        p = self.player
        if abs(p.vx) < 0.001:
            return
        direction = 1 if p.vx > 0 else -1
        edge     = p.x + p.w if direction > 0 else p.x
        tile_col = int(edge + (0.001 if direction > 0 else -0.001))
        top_row  = int(p.y)
        bot_row  = int(p.y + p.h - 0.001)
        for row in range(top_row, bot_row + 1):
            if solid_at(tiles, tile_col, row, lw, lh):
                if direction > 0:
                    p.x = float(tile_col) - p.w
                else:
                    p.x = float(tile_col + 1)
                p.vx = 0.0
                break

    def _resolve_y(self, tiles, lw, lh):
        p = self.player
        if abs(p.vy) < 0.001:
            return
        direction = 1 if p.vy > 0 else -1
        edge     = p.y + p.h if direction > 0 else p.y
        tile_row = int(edge + (0.001 if direction > 0 else -0.001))
        left_col = int(p.x)
        right_col= int(p.x + p.w - 0.001)
        for col in range(left_col, right_col + 1):
            if solid_at(tiles, col, tile_row, lw, lh):
                if direction > 0:
                    p.y = float(tile_row) - p.h
                    p.grounded = True
                else:
                    p.y = float(tile_row + 1)
                p.vy = 0.0
                break


#  Drawing

LOGO = [
    r" ██████╗ ██╗  ██╗   ██╗██████╗ ██╗  ██╗",
    r"██╔════╝ ██║  ╚██╗ ██╔╝██╔══██╗██║  ██║",
    r"██║  ███╗██║   ╚████╔╝ ██████╔╝███████║",
    r"██║   ██║██║    ╚██╔╝  ██╔═══╝ ██╔══██║",
    r"╚██████╔╝███████╗██║   ██║     ██║  ██║",
    r" ╚═════╝ ╚══════╝╚═╝   ╚═╝     ╚═╝  ╚═╝",
    r"",
    r"  ███████╗ ██████╗ ██████╗ ███╗   ███╗███████╗██████╗ ",
    r"  ██╔════╝██╔═══██╗██╔══██╗████╗ ████║██╔════╝██╔══██╗",
    r"  █████╗  ██║   ██║██████╔╝██╔████╔██║█████╗  ██████╔╝",
    r"  ██╔══╝  ██║   ██║██╔══██╗██║╚██╔╝██║██╔══╝  ██╔══██╗",
    r"  ██║     ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗██║  ██║",
    r"  ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝",
]

def draw_logo(start_row=2):
    for i, line in enumerate(LOGO):
        r.move(4, start_row + i).write(r.cyan(line))


def draw_centered(text, row, width=80, color_fn=None):
    pad = max(0, (width - len(text)) // 2)
    out = " " * pad + text
    if color_fn:
        r.move(1, row).write(color_fn(out.ljust(width)))
    else:
        r.move(1, row).write(out.ljust(width))


def draw_hline(row, width=80, char=""):
    r.move(1, row).write(r.dim(char * width))


def lives_str(lives):
    return "♥ " * lives + "♡ " * (MAX_LIVES - lives)


#  Screens

def screen_main_menu(game):
    """Returns 'play', 'select', 'quit'."""
    options = ["Play", "Level Select", "Quit"]
    sel = 0
    drain_keys()
    while True:
        clear_screen()
        draw_logo(2)
        draw_hline(16)
        for i, opt in enumerate(options):
            arrow = "▶ " if i == sel else "  "
            text  = f"{arrow}{opt}"
            row   = 18 + i * 2
            if i == sel:
                r.move(34, row).write(r.bold(r.cyan(text)))
            else:
                r.move(34, row).write(r.dim(text))
        draw_centered("WASD / Arrow Keys - Enter to Select", 25, color_fn=r.dim)
        r.flush()

        k = None
        while k is None:
            k = get_key()
            time.sleep(0.02)

        kl = k.lower()
        if kl in ("w",) or k == Key.UP:
            sel = (sel - 1) % len(options)
        elif kl in ("s",) or k == Key.DOWN:
            sel = (sel + 1) % len(options)
        elif k in (Key.ENTER, "\r", "\n", " "):
            return ["play", "select", "quit"][sel]
        elif kl == "q":
            return "quit"


def screen_level_select(game):
    """Returns chosen level index or -1 to go back."""
    sel = game.level_idx
    drain_keys()
    while True:
        clear_screen()
        r.move(1, 1).write(r.bold(r.cyan("  LEVEL SELECT")))
        draw_hline(2)

        for i, lv in enumerate(LEVELS):
            row = 4 + i * 3
            name = lv["name"]
            coins = len(lv.get("coins", []))
            best  = game.best_times.get(i)
            best_str = fmt_time(best) if best is not None else "--:--"
            arrow = "▶ " if i == sel else "  "
            num   = f"[{i+1}]"
            line  = f"{arrow}{num}  {name:<20}  Coins: {coins}   Best: {best_str}"
            if i == sel:
                r.move(4, row).write(r.bold(r.cyan(line)))
                # mini preview
                preview_tiles = lv["tiles"]
                pw = min(lv["width"], 40)
                ph = min(lv["height"], 3)
                for pr in range(ph):
                    slice_ = preview_tiles[lv["height"] - ph + pr][:pw]
                    rendered = ""
                    for ch in slice_:
                        rendered += "▓" if ch == "#" else " "
                    r.move(6, row + 1 + pr).write(r.dim(rendered))
            else:
                r.move(4, row).write(r.dim(line))

        draw_hline(4 + len(LEVELS) * 3)
        r.move(4, 5 + len(LEVELS) * 3).write(r.dim("Enter: select   Esc/Q: back"))
        r.flush()

        k = None
        while k is None:
            k = get_key()
            time.sleep(0.02)
        kl = k.lower()

        if kl in ("w",) or k == Key.UP:
            sel = (sel - 1) % len(LEVELS)
        elif kl in ("s",) or k == Key.DOWN:
            sel = (sel + 1) % len(LEVELS)
        elif k in (Key.ENTER, "\r", "\n", " "):
            return sel
        elif k in (Key.ESCAPE, "\x1b") or kl == "q":
            return -1


def screen_pause(game):
    """Returns 'resume', 'restart', 'menu', 'quit'."""
    options = ["Resume", "Restart Level", "Main Menu", "Quit"]
    sel = 0
    drain_keys()
    while True:
        # draw semi-overlay on top of existing viewport
        box_w = 30
        box_x = 2 + (VIEWPORT_W * 2 - box_w) // 2
        box_y = 3 + (VIEWPORT_H - 10) // 2

        r.move(box_x, box_y).write("┌" + "" * (box_w - 2) + "┐")
        r.move(box_x, box_y + 1).write("│" + r.bold(r.cyan("  PAUSED")).center(box_w + 20 - 2)[:box_w - 2] + "│")
        for i, opt in enumerate(options):
            arrow = "▶ " if i == sel else "  "
            text  = f"{arrow}{opt}"
            line  = text.ljust(box_w - 2)
            if i == sel:
                r.move(box_x, box_y + 3 + i).write("│" + r.bold(r.cyan(line)) + "│")
            else:
                r.move(box_x, box_y + 3 + i).write("│" + r.dim(line) + "│")
        r.move(box_x, box_y + 3 + len(options)).write("└" + "" * (box_w - 2) + "┘")
        r.flush()

        k = None
        while k is None:
            k = get_key()
            time.sleep(0.02)
        kl = k.lower()

        if kl in ("w",) or k == Key.UP:
            sel = (sel - 1) % len(options)
        elif kl in ("s",) or k == Key.DOWN:
            sel = (sel + 1) % len(options)
        elif k in (Key.ENTER, "\r", "\n", " "):
            return ["resume", "restart", "menu", "quit"][sel]
        elif k in (Key.ESCAPE, "\x1b") or kl == "p":
            return "resume"
        elif kl == "q":
            return "quit"


def screen_death(game):
    """Returns 'retry' or 'menu'."""
    drain_keys()
    clear_screen()
    msg_row = 8
    r.move(1, msg_row).write(r.bold(r.red("  ╔══════════════════════════════════════════╗")))
    if game.lives > 0:
        r.move(1, msg_row+1).write(r.bold(r.red("  ║           YOU DIED!  TRY AGAIN          ║")))
    else:
        r.move(1, msg_row+1).write(r.bold(r.red("  ║             GAME OVER                   ║")))
    r.move(1, msg_row+2).write(r.bold(r.red("  ╚══════════════════════════════════════════╝")))

    r.move(1, msg_row+4).write(f"  Lives remaining: {r.bold(lives_str(game.lives))}")
    r.move(1, msg_row+5).write(f"  Coins collected this run: {game.coins_collected}/{game.total_coins}")
    r.move(1, msg_row+6).write(f"  Time: {fmt_time(game.elapsed)}")

    if game.lives > 0:
        r.move(1, msg_row+9).write(r.bold("  [R] Retry    [M] Main Menu    [Q] Quit"))
    else:
        r.move(1, msg_row+9).write(r.bold("  [M] Main Menu    [Q] Quit"))
    r.flush()

    while True:
        k = get_key()
        if k is None:
            time.sleep(0.02)
            continue
        kl = k.lower()
        if kl == "r" and game.lives > 0:
            return "retry"
        if kl == "m":
            return "menu"
        if kl == "q":
            return "quit"


def screen_win(game):
    """Returns 'next', 'menu', or 'quit'."""
    drain_keys()
    clear_screen()
    has_next = game.level_idx + 1 < len(LEVELS)
    best = game.best_times.get(game.level_idx)

    r.move(1, 6).write(r.bold(r.cyan("  ╔══════════════════════════════════════════════╗")))
    r.move(1, 7).write(r.bold(r.cyan("  ║           LEVEL COMPLETE!                    ║")))
    r.move(1, 8).write(r.bold(r.cyan("  ╚══════════════════════════════════════════════╝")))

    r.move(1, 10).write(f"  Level: {r.bold(game.level['name'])}")
    r.move(1, 11).write(f"  Coins: {r.bold(str(game.coins_collected))}/{game.total_coins}")
    r.move(1, 12).write(f"  Time:  {r.bold(fmt_time(game.elapsed))}")
    if best is not None:
        r.move(1, 13).write(f"  Best:  {r.bold(fmt_time(best))}")

    stars = ""
    if game.coins_collected == game.total_coins:
        stars += "★★★ ALL COINS! "
    elif game.coins_collected >= game.total_coins // 2:
        stars += "★★☆ "
    else:
        stars += "★☆☆ "
    r.move(1, 15).write(f"  {r.bold(r.yellow(stars))}")

    if has_next:
        r.move(1, 18).write(r.bold("  [N] Next Level    [M] Main Menu    [Q] Quit"))
    else:
        r.move(1, 17).write(r.bold(r.cyan("  ★★★  YOU'VE BEATEN ALL LEVELS!  ★★★")))
        r.move(1, 18).write(r.bold("  [M] Main Menu    [Q] Quit"))
    r.flush()

    while True:
        k = get_key()
        if k is None:
            time.sleep(0.02)
            continue
        kl = k.lower()
        if kl == "n" and has_next:
            return "next"
        if kl == "m":
            return "menu"
        if kl == "q":
            return "quit"


def screen_all_done(game):
    drain_keys()
    clear_screen()
    draw_logo(2)
    r.move(1, 17).write(r.bold(r.yellow("  ★  YOU'VE CONQUERED GLYPHFORMER!  ★")))
    r.move(1, 19).write(r.bold("  [M] Main Menu    [Q] Quit"))
    r.flush()
    while True:
        k = get_key()
        if k is None:
            time.sleep(0.02)
            continue
        kl = k.lower()
        if kl == "m":
            return "menu"
        if kl == "q":
            return "quit"


#  Gameplay rendering

def draw_viewport(game):
    lv    = game.level
    tiles = lv["tiles"]
    lw    = lv["width"]
    lh    = lv["height"]

    target_cam = int(game.player.x) - VIEWPORT_W // 2
    cam = max(0, min(target_cam, lw - VIEWPORT_W))
    game.camera_x = cam

    spike_set = set(lv.get("spikes", []))
    coin_set  = set(game.coins_left)

    buf = []
    for row in range(VIEWPORT_H):
        line = ""
        for col_off in range(VIEWPORT_W):
            lc = cam + col_off
            if lc < 0 or lc >= lw or row >= lh:
                line += TILE_AIR
                continue
            ch = tiles[row][lc]
            if ch == "#":
                line += TILE_SOLID
            elif (lc, row) in spike_set:
                line += TILE_SPIKE
            elif (lc, row) in coin_set:
                line += TILE_COIN
            elif (lc, row) == lv["flag"]:
                line += TILE_FLAG
            else:
                line += TILE_AIR
        buf.append(f"\033[{3 + row};2H{line}")

    # Draw player
    px = 2 + int((game.player.x - cam) * 2)
    py = 3 + int(game.player.y)
    buf.append(f"\033[{py};{px}H{r.cyan(PLAYER_CHAR)}")

    # HUD
    coin_str  = f"{game.coins_collected}/{game.total_coins}"
    time_str  = fmt_time(game.elapsed)
    lives_s   = lives_str(game.lives)
    hud_left  = f" {lv['name']}  |  ◆ {coin_str}  |  ⏱ {time_str}"
    hud_right = f"  {lives_s}"
    hud_line  = hud_left + hud_right.rjust(max(0, VIEWPORT_W * 2 - len(hud_left)))
    buf.append(f"\033[1;1H{r.bold(hud_line[:VIEWPORT_W * 2 + 2])}")

    # Controls footer
    buf.append(f"\033[{3 + VIEWPORT_H};1H{r.dim('  WASD/Arrows: move & jump   S/\u2193: fast-fall   P/Esc: pause   R: restart')}")

    sys.stdout.write("".join(buf))
    sys.stdout.flush()


#  Main gameplay loop

def _process_key(game, key):
    """Process a single key during gameplay. Returns action string or None."""
    if key is None:
        return None
    kl = key.lower()
    if kl == "q":
        return "quit"
    if kl == "r":
        return "restart"
    if kl in ("p",) or key == Key.ESCAPE:
        return "pause"
    game.poll_key(key)
    return None


def _handle_pause(game):
    """Pause menu. Returns action: 'quit', 'menu', 'restart', or 'resume'."""
    draw_viewport(game)
    result = screen_pause(game)
    if result == "quit":
        return "quit"
    if result == "menu":
        return "menu"
    if result == "restart":
        return "restart"
    drain_keys()
    clear_screen()
    return "resume"


def run_level(game):
    """
    Runs the game loop for the current level.
    Returns: 'won', 'dead', 'menu', 'quit'
    """
    game.load_level(game.level_idx)
    drain_keys()
    clear_screen()

    while True:
        frame_start = time.time()

        should_tick = True

        # Input drain at start of frame
        while True:
            key = get_key()
            if key is None:
                break
            action = _process_key(game, key)
            if action == "quit":
                return "quit"
            if action == "restart":
                game.load_level(game.level_idx)
                drain_keys()
                clear_screen()
                should_tick = False
                break
            if action == "pause":
                action = _handle_pause(game)
                if action == "quit":
                    return "quit"
                if action == "menu":
                    return "menu"
                if action == "restart":
                    game.load_level(game.level_idx)
                    drain_keys()
                    clear_screen()
                    should_tick = False
                    break
                # resume: proceed to tick
                break

        if should_tick:
            dt = FRAME_TIME
            game.tick(dt)
            draw_viewport(game)

            if game.dead:
                return "dead"
            if game.won:
                return "won"

            game.clear_frame_keys()

        while time.time() - frame_start < FRAME_TIME:
            key = get_key()
            if key is not None:
                kl = key.lower()
                if kl == "q":
                    return "quit"
                if kl == "r":
                    game.load_level(game.level_idx)
                    drain_keys()
                    clear_screen()
                    break
                if kl in ("p",) or key == Key.ESCAPE:
                    action = _handle_pause(game)
                    if action == "quit":
                        return "quit"
                    if action == "menu":
                        return "menu"
                    if action == "restart":
                        game.load_level(game.level_idx)
                        drain_keys()
                        clear_screen()
                        break
                else:
                    game.poll_key(key)
            time.sleep(0.005 if is_web() else 0.002)


#  App entry point

def main(*args):
    old_settings = setup_terminal()
    r.hide_cursor()
    atexit.register(lambda: (restore_terminal(old_settings), cleanup()))

    try:
        game = Game()

        while True:
            # Main Menu
            action = screen_main_menu(game)
            if action == "quit":
                break
            if action == "select":
                idx = screen_level_select(game)
                if idx == -1:
                    continue
                game.level_idx = idx
                game.lives     = MAX_LIVES

            # Play
            while True:
                result = run_level(game)

                if result == "quit":
                    return

                if result == "menu":
                    break  # back to main menu loop

                if result == "won":
                    action = screen_win(game)
                    if action == "quit":
                        return
                    if action == "menu":
                        break
                    if action == "next":
                        game.level_idx += 1
                        game.lives = MAX_LIVES
                        if game.level_idx >= len(LEVELS):
                            action = screen_all_done(game)
                            if action == "quit":
                                return
                            break  # back to main menu
                        continue  # play next level

                if result == "dead":
                    game.lives -= 1
                    action = screen_death(game)
                    if action == "quit":
                        return
                    if action == "menu":
                        game.lives = MAX_LIVES
                        break
                    if action == "retry":
                        if game.lives <= 0:
                            game.lives = MAX_LIVES
                        continue  # retry run_level

    finally:
        restore_terminal(old_settings)
        cleanup()
