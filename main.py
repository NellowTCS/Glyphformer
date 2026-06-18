"""
Glyphformer: 2D text-based platformer with physics and WASD controls.
Runs as a pyComputer external app.
"""

import sys
import time
from pycomputersdk import Renderer, get_key, Key, Dialog, is_web, web_input_queue
from levels import LEVELS

GRAVITY = 0.5
JUMP_VEL = -3.0
MOVE_ACCEL = 0.5
FRICTION_AIR = 0.85
FRICTION_GROUND = 0.7
MAX_SPEED = 3.0
PLAYER_W = 0.8
PLAYER_H = 1.0
SUB_STEPS = 4
TARGET_FPS = 60
FRAME_TIME = 1.0 / TARGET_FPS
VIEWPORT_W = 32
VIEWPORT_H = 18

TILE_AIR = "  "
TILE_SOLID = "▓▓"
TILE_COIN = "$$"
TILE_FLAG = "FF"
PLAYER_CHARS = "@@"

r = Renderer()


def solid_at(tiles, col, row, level_w, level_h):
    if col < 0 or col >= level_w or row < 0 or row >= level_h:
        return True
    return tiles[row][col] == "#"


def aabb_overlap(ax, ay, aw, ah, bx, by, bw, bh):
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


class Player:
    def __init__(self, spawn):
        self.x = float(spawn[0]) + 0.1
        self.y = float(spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.grounded = False
        self.w = PLAYER_W
        self.h = PLAYER_H

    def reset(self, spawn):
        self.x = float(spawn[0]) + 0.1
        self.y = float(spawn[1])
        self.vx = 0.0
        self.vy = 0.0
        self.grounded = False


class Game:
    def __init__(self):
        self.level_idx = 0
        self.level = None
        self.player = None
        self.coins_left = []
        self.coins_collected = 0
        self.total_coins = 0
        self.camera_x = 0
        self.won = False
        self.dead = False
        self.all_done = False
        self.keys = {}
        self.w_pressed = False
        self.load_level(0)

    def load_level(self, idx):
        if idx >= len(LEVELS):
            self.all_done = True
            return
        self.level = LEVELS[idx]
        self.player = Player(self.level["spawn"])
        self.coins_left = list(self.level["coins"])
        self.coins_collected = 0
        self.total_coins = len(self.coins_left)
        self.camera_x = 0
        self.won = False
        self.dead = False

    def poll_key(self, key):
        if key is None:
            return

        k = key.lower()
        if k == "w":
            self.w_pressed = True
        if k == "a":
            self.keys["a"] = True
        if k == "d":
            self.keys["d"] = True
        if k == "s":
            self.keys["s"] = True

    def clear_keys(self):
        self.keys.clear()

    def tick(self):
        if self.won or self.dead or self.all_done:
            return

        accel_x = 0.0
        if self.keys.get("a"):
            accel_x -= MOVE_ACCEL
        if self.keys.get("d"):
            accel_x += MOVE_ACCEL
        fast_fall = self.keys.get("s", False)

        jump = self.w_pressed
        self.w_pressed = False

        tiles = self.level["tiles"]
        lw = self.level["width"]
        lh = self.level["height"]

        for _ in range(SUB_STEPS):
            self.player.vx += accel_x
            friction = FRICTION_AIR if not self.player.grounded else FRICTION_GROUND
            self.player.vx *= friction
            if abs(self.player.vx) > MAX_SPEED:
                self.player.vx = MAX_SPEED if self.player.vx > 0 else -MAX_SPEED
            if abs(self.player.vx) < 0.05:
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

            if jump and self.player.grounded:
                self.player.vy = JUMP_VEL
                self.player.grounded = False
                jump = False

        if self.player.y > lh:
            self.dead = True
            return

        still_left = []
        for cx, cy in self.coins_left:
            if aabb_overlap(self.player.x, self.player.y, self.player.w, self.player.h,
                            float(cx), float(cy), 1.0, 1.0):
                self.coins_collected += 1
            else:
                still_left.append((cx, cy))
        self.coins_left = still_left

        fx, fy = self.level["flag"]
        if aabb_overlap(self.player.x, self.player.y, self.player.w, self.player.h,
                        float(fx), float(fy), 1.0, 1.0):
            self.won = True

    def _resolve_x(self, tiles, lw, lh):
        p = self.player
        if abs(p.vx) < 0.001:
            return
        direction = 1 if p.vx > 0 else -1
        edge = p.x + p.w if direction > 0 else p.x
        tile_col = int(edge + (0.001 if direction > 0 else -0.001))
        top_row = int(p.y)
        bot_row = int(p.y + p.h - 0.001)

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
        edge = p.y + p.h if direction > 0 else p.y
        tile_row = int(edge + (0.001 if direction > 0 else -0.001))
        left_col = int(p.x)
        right_col = int(p.x + p.w - 0.001)

        for col in range(left_col, right_col + 1):
            if solid_at(tiles, col, tile_row, lw, lh):
                if direction > 0:
                    p.y = float(tile_row) - p.h
                    p.grounded = True
                else:
                    p.y = float(tile_row + 1)
                p.vy = 0.0
                break


def draw_viewport(g):
    lv = g.level
    tiles = lv["tiles"]
    lw = lv["width"]
    lh = lv["height"]

    target_cam = int(g.player.x) - VIEWPORT_W // 2
    cam = max(0, min(target_cam, lw - VIEWPORT_W))
    g.camera_x = cam

    for row in range(VIEWPORT_H):
        line = ""
        for col_off in range(VIEWPORT_W):
            lc = cam + col_off
            if lc < 0 or lc >= lw or row >= lh:
                line += TILE_AIR
            else:
                ch = tiles[row][lc]
                if ch == "#":
                    line += TILE_SOLID
                elif (lc, row) in g.coins_left:
                    line += TILE_COIN
                elif (lc, row) == lv["flag"]:
                    line += TILE_FLAG
                else:
                    line += TILE_AIR
        r.move(2, 3 + row).write(line)

    px = 2 + int((g.player.x - cam) * 2)
    py = 3 + int(g.player.y)
    r.move(px, py).write(r.cyan(PLAYER_CHARS))

    coin_str = f"{g.coins_collected}/{g.total_coins}"
    hud = f" {lv['name']}  |  Coins: {coin_str}  |  WASD: move/jump  R: restart  Q: quit  "
    r.move(1, 1).write(r.bold(hud.ljust(80)))
    r.flush()


def draw_overlay(title, lines):
    box_w = max(30, max(len(l) for l in lines) + 4)
    box_h = len(lines) + 2
    dialog = Dialog(title=title, message="\n".join(lines), buttons=[],
                    x=0, y=0, width=box_w, height=box_h)
    dl = dialog.render().splitlines()
    pad_x = 2 + (VIEWPORT_W * 2 - box_w) // 2
    pad_y = 3 + (VIEWPORT_H - box_h) // 2
    for i, line in enumerate(dl):
        r.move(pad_x, pad_y + i).write(line[:box_w].ljust(box_w))
    r.flush()


def main(*args):
    from pycomputersdk import setup_raw as setup_terminal, restore as restore_terminal, cleanup

    game = Game()
    old_settings = setup_terminal()
    r.hide_cursor()

    try:
        sys.stdout.write("\033[2J\033[1;1H")
        r.move(1, 1).write(r.bold("  GLYPHFORMER  "))
        r.move(1, 3).write("  WASD to move and jump.  Collect coins, reach the flag.")
        r.move(1, 5).write(r.bold("  Press any key to start..."))
        r.flush()

        while get_key() is None:
            time.sleep(0.05)

        game.load_level(0)

        while not game.all_done:
            frame_start = time.time()

            while True:
                key = get_key()
                if key is None:
                    break

                k = key.lower()

                if k == "q":
                    restore_terminal(old_settings)
                    cleanup()
                    return

                if k == "r":
                    game.player.reset(game.level["spawn"])
                    game.coins_left = list(game.level["coins"])
                    game.coins_collected = 0
                    game.dead = False
                    game.won = False
                    continue

                game.poll_key(key)

            game.tick()

            draw_viewport(game)

            if game.dead:
                draw_overlay("YOU FELL", ["R: restart", "Q: quit"])
                while True:
                    k = get_key()
                    if k is None:
                        break
                    if k.lower() == "q":
                        restore_terminal(old_settings)
                        cleanup()
                        return
                    if k == "r":
                        game.player.reset(game.level["spawn"])
                        game.coins_left = list(game.level["coins"])
                        game.coins_collected = 0
                        game.dead = False
                        break

            if game.won:
                if game.level_idx + 1 >= len(LEVELS):
                    draw_overlay("YOU WIN!", ["All levels complete!", "", "Q: quit"])
                else:
                    draw_overlay("LEVEL COMPLETE", ["R: next level", "Q: quit"])
                while True:
                    k = get_key()
                    if k is None:
                        break
                    if k.lower() == "q":
                        restore_terminal(old_settings)
                        cleanup()
                        return
                    if k == "r" and game.level_idx + 1 < len(LEVELS):
                        game.level_idx += 1
                        game.load_level(game.level_idx)
                        break

            game.clear_keys()

            elapsed = time.time() - frame_start
            sleep_time = max(0, FRAME_TIME - elapsed)
            time.sleep(sleep_time)

    finally:
        restore_terminal(old_settings)
        cleanup()
