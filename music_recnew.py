#!/usr/bin/env python3
# Pygame Music Recommender (Teacher Solution) — loads dataset.csv and filters by fuzzy category

import pygame
import numpy as np
import pandas as pd
import os
import textwrap

# --- Setup ---
DATA_FILE = r"C:\Users\willi\Desktop\fuzzy_logic\dataset.csv"


def trapmf(x, a, b, c, d):
    y = np.zeros_like(x, dtype=float)
    if b > a:
        m = (x > a) & (x < b)
        y[m] = (x[m] - a) / (b - a)
    y[(x >= b) & (x <= c)] = 1.0
    if d > c:
        m = (x > c) & (x < d)
        y[m] = (d - x[m]) / (d - c)
    return y


U = np.arange(0, 11, 1)
low = trapmf(U, 0, 0, 3, 5)
mid = trapmf(U, 4, 5, 6, 7)
high = trapmf(U, 6, 7, 10, 10)

mor = trapmf(U, 0, 0, 2, 4)
aft = trapmf(U, 3, 5, 6, 7)
nig = trapmf(U, 6, 8, 10, 10)


def mu(arr, x):
    return float(np.interp(x, U, arr))


def fuzzy_recommend(mood, energy, time):
    S, N, H = mu(low, mood), mu(mid, mood), mu(high, mood)
    T, O, E = mu(low, energy), mu(mid, energy), mu(high, energy)
    M, A, Nn = mu(mor, time), mu(aft, time), mu(nig, time)

    chill = max(min(S, T), min(Nn, T), min(M, T))
    standard = max(min(N, O), min(A, O), min(N, E))
    party = max(min(H, E), min(Nn, E), min(A, H, E))
    gym = max(min(E, N), min(E, H))
    dance = min(E, H)


    if party >= standard and party >= chill and party >= gym and party >= dance:
        return "Party"
    if gym >= standard and gym >= chill and gym >= dance:
        return "Gym"
    if dance >= standard and dance >= chill and dance >= party and dance >= gym:
        return "Dance"
    if chill >= standard and chill >= party and chill >= gym and chill >= dance:
        return "Chill"
    return "Standard"


def pick_songs(df, category, n=10):
    if "valence" in df.columns and "energy" in df.columns:
        if category == "Chill":
            pool = df[(df["valence"] <= 0.45) & (df["energy"] <= 0.5)]
        elif category == "Party":
            pool = df[(df["valence"] >= 0.55) & (df["energy"] >= 0.6)]
        elif category == "Gym":
            pool = df[(df["energy"] >= 0.7)]
        elif category == "Dance":
            pool = df[(df["valence"] >= 0.6) & (df["energy"] >= 0.6)]
        else:  # Standard
            pool = df[
                (df["valence"] > 0.4) & (df["valence"] < 0.6)
                & (df["energy"] > 0.4) & (df["energy"] < 0.6)
            ]
    else:
        pool = df

    if len(pool) == 0:
        pool = df
    return pool.sample(min(n, len(pool)), random_state=42)


# --- Helper: draw wrapped text ---
def draw_text(surface, text, pos, font, color, max_width):
    """Draw text with wrapping"""
    x, y = pos
    lines = textwrap.wrap(text, width=max_width // font.size(" ")[0])
    for line in lines:
        surface.blit(font.render(line, True, color), (x, y))
        y += font.get_linesize()


def main():
    pygame.init()

    # --- FULLSCREEN mode ---
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    WIDTH, HEIGHT = screen.get_size()
    clock = pygame.time.Clock()

    font = pygame.font.SysFont("consolas", 24)
    small = pygame.font.SysFont("consolas", 20)

    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        print("Failed to load dataset.csv:", e)
        return

    sliders = {"Mood": 5.0, "Energy": 5.0, "Time": 5.0}
    dragging = None
    songs = None
    category = "Standard"
    running = True

    while running:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                    category = fuzzy_recommend(
                        sliders["Mood"], sliders["Energy"], sliders["Time"]
                    )
                    songs = pick_songs(df, category, n=10)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                mx, my = e.pos
                for i, key in enumerate(sliders):
                    x, y = 200, 150 + i * 120
                    if x <= mx <= x + 500 and y - 10 <= my <= y + 10:
                        dragging = key
            elif e.type == pygame.MOUSEBUTTONUP:
                dragging = None
            elif e.type == pygame.MOUSEMOTION and dragging:
                mx, _ = e.pos
                sliders[dragging] = float(np.clip((mx - 200) / 500 * 10, 0, 10))

        # --- Drawing ---
        screen.fill((250, 250, 255))

        draw_text(
            screen,
            "Fuzzy Music Recommender — Press ENTER/SPACE to recommend",
            (20, 20),
            font,
            (30, 30, 60),
            WIDTH - 40,
        )

        for i, (key, val) in enumerate(sliders.items()):
            y = 150 + i * 120
            pygame.draw.rect(screen, (220, 220, 230), (200, y - 3, 500, 6), border_radius=3)
            x = 200 + int(val / 10 * 500)
            pygame.draw.circle(screen, (80, 120, 200), (x, y), 10)
            screen.blit(font.render(f"{key}: {val:4.1f}", True, (30, 30, 60)), (720, y - 12))

        screen.blit(font.render(f"Category: {category}", True, (20, 80, 30)), (200, 520))

        if songs is not None:
            y_start = 560
            for i, row in songs.reset_index(drop=True).iterrows():
                title = str(row.get("track_name", row.get("name", "Unknown Title")))
                artist = str(row.get("artists", "Unknown Artist"))
                line = f"{i+1:2d}. {title} — {artist}"
                draw_text(screen, line, (200, y_start + i * 50), small, (40, 40, 40), WIDTH - 400)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()