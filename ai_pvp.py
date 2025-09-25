#!/usr/bin/env python3
# Pygame Enemy AI — fuzzy decides Flee/Defend/Attack
import pygame, numpy as np

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

    s_flee = max(min(Dn, EL), min(Dn, PL))
    s_defend = max(min(Dm, EM), min(Df, EM), min(Dm, PM))
    s_attack = max(min(Dn, PH, EH), min(Dn, PL, EH), min(Dm, PH, EH), min(Df, PH, EH))

    if s_attack >= s_defend and s_attack >= s_flee:
        return "Attack"
    if s_flee >= s_defend:
        return "Flee"
    return "Defend"

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)

    player = pygame.Vector2(WIDTH * 0.3, HEIGHT * 0.5)
    enemy = pygame.Vector2(WIDTH * 0.7, HEIGHT * 0.5)
    p_hp, e_hp = 7.0, 7.0

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

        # Drawing
        screen.fill((245, 246, 250))
        pygame.draw.circle(screen, (40, 130, 200), (int(player.x), int(player.y)), 14)
        pygame.draw.circle(screen, (200, 60, 60), (int(enemy.x), int(enemy.y)), 16)
        pygame.draw.line(screen, (120, 120, 160), player, enemy, 1)

        info = f"Action:{action} Dist:{dist_px:5.1f} PlayerHP:{p_hp:.1f} (Q/W) EnemyHP:{e_hp:.1f} (O/P)"
        screen.blit(font.render(info, True, (30, 30, 30)), (10, 10))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
