#!/usr/bin/env python3
"""
Fuzzy AGV (Python/Pygame) — feature‑complete teaching demo
----------------------------------------------------------
What you get:
 - Multiple preset tracks (switch with keys 1..5)
 - Live draw/erase walls (D to toggle, Left click=draw wall, Right click=erase)
 - Car with 3 ray sensors (front/left/right) that measure distance to nearest wall
 - Fuzzy controller (scikit‑fuzzy) maps distances -> steering angle
 - Start/Pause/Reset, speed control, sensor & debug overlays
 - Highly commented code for classroom use

Controls (while window focused):
  [S]  Start/Pause simulation
  [R]  Reset car on current track
  [C]  Center car & reset heading
  [1..5] Switch track preset
  [D]  Toggle draw/erase mode (mouse left=draw, right=erase)
  [T]  Toggle sensor rays on/off
  [F]  Toggle fuzzy debug overlay
  [+/-] Increase/Decrease car speed
  [H]  Toggle help overlay
  [ESC] Quit

Dependencies:
  pip install pygame numpy scikit-fuzzy

Note for educators:
 - Membership functions and rules mirror the classic AForge FuzzyAGV sample:
   Inputs (0..120): Near, Medium, Far (trapezoids)
   Output (-50..50 deg): VeryNegative, Negative, LittleNegative, Zero,
                         LittlePositive, Positive, VeryPositive
 - Rules are annotated at the bottom of this file in RULES_TEXT.
"""

import math
import sys
import time
import pygame
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# ---------------------------- Config ---------------------------- #
WIDTH, HEIGHT = 1240,1000
FPS = 60
GRID = 10               # grid cell size in pixels
SENSOR_MAX = 120        # max sensor distance (match fuzzy universe upper bound)
CAR_LEN = 24            # visual length (pixels)
CAR_WID = 14            # visual width (pixels)
BG = (245, 246, 250)
INK = (33, 33, 33)
WALL = (40, 40, 40)
CAR_COLOR = (200, 50, 50)
SENSOR_COLOR = (0, 120, 200)
DEBUG_COLOR = (10, 100, 10)

# ---------------------- Track Presets (grids) ------------------- #
# Grid is 0 = empty, 1 = wall. We'll build from simple patterns.
def blank_grid(cols, rows):
    return np.zeros((rows, cols), dtype=np.uint8)

def rectangle_track(cols, rows, thickness=2):
    g = blank_grid(cols, rows)
    g[5:rows-5, 5:5+thickness] = 1
    g[5:rows-5, cols-5-thickness:cols-5] = 1
    g[5:5+thickness, 5:cols-5] = 1
    g[rows-5-thickness:rows-5, 5:cols-5] = 1
    # opening as "gate"
    g[rows//2-2:rows//2+2, 5:5+thickness] = 0
    return g

def s_track(cols, rows):
    g = blank_grid(cols, rows)
    # vertical corridor with S kinks
    for x in range(10, cols-10):
        y_top = int(10 + 10*math.sin(x/8.0))
        y_bot = rows - y_top - 1
        g[y_top:y_top+2, x] = 1
        g[y_bot-2:y_bot, x] = 1
    return g

def figure_eight(cols, rows):
    g = blank_grid(cols, rows)
    cx, cy = cols//2, rows//2
    r = min(cols, rows)//4
    for a in np.linspace(0, 2*math.pi, 1500):
        x1 = int(cx - r*math.cos(a))
        y1 = int(cy - r*math.sin(a))
        x2 = int(cx + r*math.cos(a))
        y2 = int(cy + r*math.sin(a))
        if 0 <= x1 < cols and 0 <= y1 < rows:
            g[y1, x1] = 1
        if 0 <= x2 < cols and 0 <= y2 < rows:
            g[y2, x2] = 1
    # thicken lines
    kern = [(0,0),(1,0),(-1,0),(0,1),(0,-1)]
    g2 = g.copy()
    ys, xs = np.where(g==1)
    for y,x in zip(ys,xs):
        for dx,dy in kern:
            if 0 <= x+dx < g.shape[1] and 0 <= y+dy < g.shape[0]:
                g2[y+dy,x+dx] = 1
    return g2

def zigzag_corridor(cols, rows):
    g = blank_grid(cols, rows)
    x = 8
    y = 8
    dx = 1
    for step in range(cols-16):
        top = y
        bot = rows - y - 1
        g[top:top+2, x] = 1
        g[bot-2:bot, x] = 1
        x += 1
        y += dx
        if y < 6 or y > rows//2 - 6:
            dx *= -1
    return g

def border_maze(cols, rows):
    g = rectangle_track(cols, rows, thickness=2)
    # add some pillars and bars
    for i in range(10, rows-10, 8):
        g[i:i+2, cols//3:cols//3+1] = 1
        g[i:i+2, 2*cols//3:2*cols//3+1] = 1
    for j in range(12, cols-12, 10):
        g[rows//3:rows//3+1, j:j+2] = 1
        g[2*rows//3:2*rows//3+1, j:j+2] = 1
    return g

TRACK_BUILDERS = [
    ("Rectangle", rectangle_track),
    ("S‑Track", s_track),
    ("Figure 8", figure_eight),
    ("ZigZag", zigzag_corridor),
    ("Border Maze", border_maze),
]

# -------------------------- Fuzzy Logic ------------------------- #
# Antecedents (inputs): FrontalDistance, LeftDistance, RightDistance (0..120)
# Consequent (output): Angle (-50..50 degrees)
front = ctrl.Antecedent(np.arange(0, SENSOR_MAX+0.1, 0.5), 'FrontalDistance')
left  = ctrl.Antecedent(np.arange(0, SENSOR_MAX+0.1, 0.5), 'LeftDistance')
right = ctrl.Antecedent(np.arange(0, SENSOR_MAX+0.1, 0.5), 'RightDistance')
angle = ctrl.Consequent(np.arange(-50, 50.1, 0.5), 'Angle')

# Membership functions (mirroring the C# AForge demo shape & names)
# Distances share the same tri/trap shapes: Near, Medium, Far
def define_distance_terms(var):
    # Tuned to trigger avoidance earlier so it won't drive into walls
    var['Near']   = fuzz.trapmf(var.universe, [0, 0, 45, 85])
    var['Medium'] = fuzz.trapmf(var.universe, [45, 85, 95, 115])
    var['Far']    = fuzz.trapmf(var.universe, [85, 115, SENSOR_MAX, SENSOR_MAX])

for v in (front, left, right):
    define_distance_terms(v)

# Output angle membership functions
# Convention: Positive = steer RIGHT (heading increases, clockwise on screen)
#             Negative = steer LEFT  (heading decreases)
angle['VeryNegative']   = fuzz.trapmf(angle.universe, [-50, -50, -40, -35])
angle['Negative']       = fuzz.trapmf(angle.universe, [-40, -35, -25, -20])
angle['LittleNegative'] = fuzz.trapmf(angle.universe, [-25, -20, -10, -5])
angle['Zero']           = fuzz.trimf(angle.universe,  [-10, 0, 10])
angle['LittlePositive'] = fuzz.trapmf(angle.universe, [5, 10, 20, 25])
angle['Positive']       = fuzz.trapmf(angle.universe, [20, 25, 35, 40])
angle['VeryPositive']   = fuzz.trapmf(angle.universe, [35, 40, 50, 50])

# Rules (annotated below in RULES_TEXT). These correspond closely to the AForge sample.
rules = [
    # 1) Open road ahead ⇒ keep steering centered.
    ctrl.Rule(front['Far'], angle['Zero']),

    # 2) Everything is far ⇒ keep straight.
    ctrl.Rule(front['Far'] & right['Far'] & left['Far'], angle['Zero']),

    # 3) Too close on right but left not close ⇒ steer slightly left (negative is left here).
    ctrl.Rule(right['Near'] & ~left['Near'], angle['LittleNegative']),

    # 4) Too close on left but right not close ⇒ steer slightly right.
    ctrl.Rule(~right['Near'] & left['Near'], angle['LittlePositive']),

    # 5) Wall ahead & space on right ⇒ turn right.
    ctrl.Rule(right['Far'] & front['Near'], angle['Positive']),

    # 6) Wall ahead & space on left ⇒ turn left.
    ctrl.Rule(left['Far'] & front['Near'], angle['Negative']),

    # 7) Tight corridor (both sides far but front near) ⇒ prefer right turn a bit.
    ctrl.Rule(right['Far'] & left['Far'] & front['Near'], angle['Positive']),

    # 8) Front medium, right near ⇒ nudge left.
    ctrl.Rule(front['Medium'] & right['Near'], angle['LittleNegative']),

    # 9) Front medium, left near ⇒ nudge right.
    ctrl.Rule(front['Medium'] & left['Near'], angle['LittlePositive']),

    # 10) Front near & both sides near ⇒ sharpest turn to whichever side is a tad freer.
    ctrl.Rule(front['Near'] & right['Near'] & ~left['Near'], angle['Negative']),
    ctrl.Rule(front['Near'] & left['Near'] & ~right['Near'], angle['Positive']),

    # 11) Dead‑end (all near) ⇒ pick a strong right bias (arbitrary, prevents dithering).
    ctrl.Rule(front['Near'] & right['Near'] & left['Near'], angle['VeryPositive']),
]

system = ctrl.ControlSystem(rules)
sim = ctrl.ControlSystemSimulation(system)


# ------------------------- Pygame Setup ------------------------- #
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Fuzzy AGV — Python/Pygame")
clock = pygame.time.Clock()
font_small = pygame.font.SysFont("consolas", 16)
font_big = pygame.font.SysFont("consolas", 20)

COLS = WIDTH // GRID
ROWS = HEIGHT // GRID

# Current track grid
current_track_idx = 0
grid = TRACK_BUILDERS[current_track_idx][1](COLS, ROWS)

# --------------------------- Car State -------------------------- #
class Car:
    def __init__(self):
        self.x = WIDTH*0.2
        self.y = HEIGHT*0.5
        self.heading = 0.0         # degrees, 0 = east, CCW positive
        self.speed = 90.0 / FPS    # pixels per frame
        self.steering = 0.0        # degrees per inference
        self.sensor_angles = [0, -45, 45]  # front, left(-), right(+), relative to heading
        self.history = []          # breadcrumb trail

    def reset(self):
        self.__init__()

    def center(self):
        self.x = WIDTH/2
        self.y = HEIGHT/2
        self.heading = 0.0
        self.steering = 0.0
        self.history.clear()

car = Car()

# ---------------------- Grid / Drawing Modes -------------------- #
draw_mode = False
show_help = True
show_sensors = True
show_debug = True
mouse_down_left = False
mouse_down_right = False

def set_grid_cell(px, py, val):
    gx = int(px // GRID)
    gy = int(py // GRID)
    if 0 <= gx < COLS and 0 <= gy < ROWS:
        grid[gy, gx] = 1 if val else 0

# --------------------------- Sensors ---------------------------- #
def raycast_distance(x, y, angle_deg, max_dist=SENSOR_MAX):
    """Cast a ray from (x,y) at angle_deg (degrees), step along until wall hit or max_dist."""
    ang = math.radians(angle_deg)
    step = 2.0  # pixels
    dist = 0.0
    while dist < max_dist:
        rx = x + math.cos(ang) * dist
        ry = y + math.sin(ang) * dist
        gx = int(rx // GRID)
        gy = int(ry // GRID)
        if gx < 0 or gx >= COLS or gy < 0 or gy >= ROWS:
            return dist
        if grid[gy, gx] == 1:
            return dist
        dist += step
    return max_dist

def sense(car):
    """Return (front, left, right) distances in pixels, clipped to SENSOR_MAX."""
    vals = []
    for rel in car.sensor_angles:
        a = car.heading + rel
        d = raycast_distance(car.x, car.y, a, SENSOR_MAX)
        vals.append(min(d, SENSOR_MAX))
    # Order: front, left, right (left sensor is at -45 rel, but we placed index 1 accordingly)
    # sensor_angles are [0, -45, +45] already in (front,left,right) order
    return tuple(vals)

# ----------------------- Fuzzy Controller ----------------------- #
def fuzzy_steer(front_val, left_val, right_val):
    """Compute steering angle (degrees) given three distances (pixels).
    Robust to edge cases where no rule fires or inputs are out-of-range.
    """
    # Clip inputs to universes
    fv = float(np.clip(front_val, 0, SENSOR_MAX))
    lv = float(np.clip(left_val,  0, SENSOR_MAX))
    rv = float(np.clip(right_val, 0, SENSOR_MAX))
    try:
        sim.input['FrontalDistance'] = fv
        sim.input['LeftDistance'] = lv
        sim.input['RightDistance'] = rv
        sim.compute()
        # Some scikit-fuzzy versions omit the key if computation failed silently
        if 'Angle' not in sim.output or np.isnan(sim.output['Angle']):
            return 0.0
        return float(sim.output['Angle'])
    except Exception:
        # Failsafe steering: turn toward the freer side if very close ahead
        if fv < 25:
            return 25.0 if rv >= lv else -25.0
        return 0.0

# ------------------------- Simulation Step ---------------------- #
def update(car, dt):
    # 1) Sense
    fd, ld, rd = sense(car)

    # 2) Fuzzy decide steering (how many degrees to turn this frame group)
    steering_change = fuzzy_steer(fd, ld, rd)
    # Smooth steering (slightly more responsive)
    car.steering = 0.7*car.steering + 0.3*steering_change

    # Emergency nudge if very close to a wall ahead: turn toward the freer side
    if fd < 25:
        if rd > ld:
            car.steering += 20.0
        elif ld > rd:
            car.steering -= 20.0
        else:
            car.steering += 20.0  # default right bias

    # 3) Apply heading & move forward (scale with dt)
    car.heading += car.steering * dt * 1.6
    # clamp heading to [-180,180] for numeric neatness
    if car.heading > 180: car.heading -= 360
    if car.heading < -180: car.heading += 360

    dx = math.cos(math.radians(car.heading)) * car.speed * dt * FPS
    dy = math.sin(math.radians(car.heading)) * car.speed * dt * FPS

    newx = car.x + dx
    newy = car.y + dy

    # 4) Collision: stop before wall; if collided, nudge heading slightly
    gx = int(newx // GRID)
    gy = int(newy // GRID)
    if 0 <= gx < COLS and 0 <= gy < ROWS and grid[gy, gx] == 1:
        # Collision reaction: back off
        car.x -= math.cos(math.radians(car.heading)) * 4
        car.y -= math.sin(math.radians(car.heading)) * 4
        # Turn away from the nearer wall using sensor info
        if rd < ld:
            car.heading -= 25  # wall on right: steer left
        else:
            car.heading += 25  # wall on left (or equal): steer right
    else:
        car.x = newx
        car.y = newy

    # Leave a breadcrumb
    if len(car.history) == 0 or (abs(car.x - car.history[-1][0]) + abs(car.y - car.history[-1][1])) > 4:
        car.history.append((car.x, car.y))

    return (fd, ld, rd), steering_change

# ---------------------------- Drawing --------------------------- #
def draw_grid(surface):
    surface.fill(BG)
    # walls
    ys, xs = np.where(grid == 1)
    for y, x in zip(ys, xs):
        pygame.draw.rect(surface, WALL, (x*GRID, y*GRID, GRID, GRID))

def draw_car(surface, car):
    # Draw trail
    if len(car.history) > 1:
        pygame.draw.lines(surface, (180, 180, 220), False, car.history, 2)

    # Car body as oriented rectangle
    ang = math.radians(car.heading)
    cos, sin = math.cos(ang), math.sin(ang)
    half_l = CAR_LEN/2
    half_w = CAR_WID/2
    corners = []
    for sx, sy in [(-half_l, -half_w), (half_l, -half_w), (half_l, half_w), (-half_l, half_w)]:
        rx = car.x + sx*cos - sy*sin
        ry = car.y + sx*sin + sy*cos
        corners.append((rx, ry))
    pygame.draw.polygon(surface, CAR_COLOR, corners)
    # heading line
    nose = (car.x + half_l*cos, car.y + half_l*sin)
    pygame.draw.line(surface, (20,20,20), (car.x, car.y), nose, 2)

def draw_sensors(surface, car, sensor_values):
    for rel, dist in zip(car.sensor_angles, sensor_values):
        a = math.radians(car.heading + rel)
        p2 = (car.x + math.cos(a)*dist, car.y + math.sin(a)*dist)
        pygame.draw.line(surface, SENSOR_COLOR, (car.x, car.y), p2, 2)
        pygame.draw.circle(surface, SENSOR_COLOR, (int(p2[0]), int(p2[1])), 3)

def draw_text(surface, text, x, y, color=INK, big=False):
    f = font_big if big else font_small
    s = f.render(text, True, color)
    surface.blit(s, (x, y))

def draw_help(surface):
    lines = [
        "S=Start/Pause  R=Reset  C=Center  1..5=Track   D=Draw/Erase  T=Sensors  F=Fuzzy Debug  +/-=Speed  H=Help  ESC=Quit",
        f"Track: {TRACK_BUILDERS[current_track_idx][0]}   DrawMode: {'ON' if draw_mode else 'off'}",
    ]
    y=5
    for ln in lines:
        draw_text(surface, ln, 8, y, (0,0,0), big=False)
        y += 18

def draw_debug(surface, fd, ld, rd, steering):
    y = HEIGHT-120
    draw_text(surface, f"Front: {fd:5.1f}  Left: {ld:5.1f}  Right: {rd:5.1f}  ->  angle: {steering:6.2f} deg", 8, y, DEBUG_COLOR)
    y += 18

# ----------------------------- Main ----------------------------- #
def main():
    global draw_mode, current_track_idx, grid, show_help, show_sensors, show_debug

    running = True
    paused = False
    last_time = time.time()

    while running:
        now = time.time()
        dt = now - last_time
        last_time = now

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_s:
                    paused = not paused
                elif event.key == pygame.K_r:
                    car.reset()
                elif event.key == pygame.K_c:
                    car.center()
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    idx = event.key - pygame.K_1
                    if 0 <= idx < len(TRACK_BUILDERS):
                        current_track_idx = idx
                        grid = TRACK_BUILDERS[idx][1](COLS, ROWS)
                        car.reset()
                elif event.key == pygame.K_d:
                    draw_mode = not draw_mode
                elif event.key == pygame.K_t:
                    show_sensors = not show_sensors
                elif event.key == pygame.K_f:
                    show_debug = not show_debug
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    car.speed = min(car.speed + 10.0/FPS, 240.0/FPS)
                elif event.key == pygame.K_MINUS:
                    car.speed = max(car.speed - 10.0/FPS, 10.0/FPS)
                elif event.key == pygame.K_h:
                    show_help = not show_help

        # Draw/Erase with mouse while in draw_mode
        if draw_mode:
            buttons = pygame.mouse.get_pressed(3)
            if any(buttons):
                mx, my = pygame.mouse.get_pos()
                if buttons[0]:  # left = draw wall
                    set_grid_cell(mx, my, 1)
                if buttons[2]:  # right = erase
                    set_grid_cell(mx, my, 0)

        # Update
        if not paused:
            (fd, ld, rd), steering = update(car, dt)
        else:
            (fd, ld, rd) = sense(car)
            steering = 0.0

        # Render
        draw_grid(screen)
        draw_car(screen, car)
        if show_sensors:
            draw_sensors(screen, car, (fd, ld, rd))
        if show_help:
            draw_help(screen)
        if show_debug:
            draw_debug(screen, fd, ld, rd, steering)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
