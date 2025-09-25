#!/usr/bin/env python3
# Pygame Enemy AI — fuzzy decides Flee/Defend/Attack with combat + player attack + game over + boundaries
import pygame, numpy as np, time, sys

WIDTH, HEIGHT = 800, 600
PLAYER_SPEED = 200
ENEMY_SPEED = 140

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

# Fuzzy sets
U = np.arange(0, 11, 1)
dist_near = trapmf(U, 0, 0, 2, 5)
dist_med = trapmf(U, 3, 5, 6, 8)
dist_far = trapmf(U, 6, 8, 10, 10)

low = trapmf(U, 0, 0, 3, 5)
med = trapmf(U, 4, 5, 6, 7)
high = trapmf(U, 6, 7, 10, 10)

def mu(arr, x): 
    return float(np.interp(x, U, arr))

def fuzzy_decide(distance, p_hp, e_hp):
    Dn, Dm, Df = mu(dist_near, distance), mu(dist_med, distance), mu(dist_far, distance)
    PL, PM, PH = mu(low, p_hp), mu(med, p_hp), mu(high, p_hp)
    EL, EM, EH = mu(low, e_hp), mu(med, e_hp), mu(high, e_hp)

    # Balanced rules
    s_flee = max(min(Dn, EL), min(Dm, EL), EL)
    s_defend = max(min(Dm, EM), min(Dm, EL), min(Df, EM), min(Df, EL), min(Dm, PM))
    s_attack = max(min(Dn, PH, EH), min(Dm, PH, EH), min(Df, PH, EH))

    if s_attack >= s_defend and s_attack >= s_flee:
        return "Attack"
    if s_flee >= s_defend:
        return "Flee"
    return "Defend"

def draw_hp_bar(screen, pos, hp, max_hp=10, width=60, height=8):
    """Draws an HP bar centered at pos."""
    x, y = pos
    pygame.draw.rect(screen, (200, 50, 50), (x - width // 2, y, width, height))  # background
    hp_width = int(width * (hp / max_hp))
    pygame.draw.rect(screen, (50, 200, 50), (x - width // 2, y, hp_width, height))  # current HP
    pygame.draw.rect(screen, (30, 30, 30), (x - width // 2, y, width, height), 2)  # border

def game_over(screen, font, winner):
    """Show game over screen and wait a few seconds."""
    screen.fill((20, 20, 20))
    msg = f"GAME OVER — {winner} wins!"
    text = font.render(msg, True, (240, 240, 240))
    rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    screen.blit(text, rect)
    pygame.display.flip()
    pygame.time.wait(3000)
    pygame.quit()
    sys.exit()

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 22, bold=True)

    player = pygame.Vector2(WIDTH * 0.3, HEIGHT * 0.5)
    enemy = pygame.Vector2(WIDTH * 0.7, HEIGHT * 0.5)
    p_hp, e_hp = 7.0, 7.0

    last_hit_time = 0
    hit_cooldown = 0.8  # seconds

    last_attack_time = 0
    attack_cooldown = 0.6  # seconds (for player attack)

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE: 
                    running = False
                elif e.key == pygame.K_q: 
                    p_hp = max(0, p_hp - 1)
                elif e.key == pygame.K_w: 
                    p_hp = min(10, p_hp + 1)
                elif e.key == pygame.K_o: 
                    e_hp = max(0, e_hp - 1)
                elif e.key == pygame.K_p: 
                    e_hp = min(10, e_hp + 1)

        # Player movement
        keys = pygame.key.get_pressed()
        vel = pygame.Vector2(
            keys[pygame.K_RIGHT] - keys[pygame.K_LEFT],
            keys[pygame.K_DOWN] - keys[pygame.K_UP]
        )
        if vel.length_squared():
            vel = vel.normalize() * PLAYER_SPEED * dt
        player += vel
        player.x = max(10, min(WIDTH - 10, player.x))
        player.y = max(10, min(HEIGHT - 10, player.y))

        # Enemy decision-making
        delta = player - enemy
        dist_px = delta.length()
        action = fuzzy_decide(min(dist_px / 40, 10), p_hp, e_hp)
        dir = delta.normalize() if dist_px > 0 else pygame.Vector2(1, 0)

        if action == "Attack":
            enemy += dir * ENEMY_SPEED * dt
        elif action == "Flee":
            enemy -= dir * ENEMY_SPEED * dt
        else:  # Defend
            target = dist_px - 160
            enemy += dir * (target * 0.8) * dt

        # Clamp enemy inside the screen
        enemy.x = max(10, min(WIDTH - 10, enemy.x))
        enemy.y = max(10, min(HEIGHT - 10, enemy.y))

        # Combat check (collision damage)
        now = time.time()
        if dist_px < (14 + 16):  # touching
            if now - last_hit_time > hit_cooldown:
                if action == "Attack":
                    p_hp = max(0, p_hp - 1)
                else:  # Defend or Flee
                    e_hp = max(0, e_hp - 1)
                last_hit_time = now

        # Player attack (SPACE)
        if keys[pygame.K_SPACE] and dist_px < 40:  # close enough
            if now - last_attack_time > attack_cooldown:
                e_hp = max(0, e_hp - 1)
                last_attack_time = now

        # Check for game over
        if p_hp <= 0:
            game_over(screen, font, "Enemy")
        if e_hp <= 0:
            game_over(screen, font, "Player")

        # Drawing
        screen.fill((245, 246, 250))
        pygame.draw.circle(screen, (40, 130, 200), (int(player.x), int(player.y)), 14)
        pygame.draw.circle(screen, (200, 60, 60), (int(enemy.x), int(enemy.y)), 16)
        pygame.draw.line(screen, (120, 120, 160), player, enemy, 1)

        draw_hp_bar(screen, (int(player.x), int(player.y) - 28), p_hp)
        draw_hp_bar(screen, (int(enemy.x), int(enemy.y) - 32), e_hp)

        info = f"Action:{action} Dist:{dist_px:5.1f} PlayerHP:{p_hp:.1f} EnemyHP:{e_hp:.1f}"
        screen.blit(font.render(info, True, (30, 30, 30)), (10, 10))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
