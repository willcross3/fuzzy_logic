import numpy as np
import skfuzzy as fuzz

# --- Universes ---
x_food    = np.arange(0, 11, 1)
x_service = np.arange(0, 11, 1)
x_tip     = np.arange(0, 31, 1)

# --- Membership functions ---
food_rancid    = fuzz.trapmf(x_food,    [0, 0, 2, 4])
food_fine      = fuzz.trapmf(x_food,    [3, 5, 6, 7])
food_delicious = fuzz.trapmf(x_food,    [6, 8, 10, 10])

service_poor      = fuzz.trapmf(x_service, [0, 0, 2, 5])
service_good      = fuzz.trapmf(x_service, [4, 5, 6, 7])
service_excellent = fuzz.trapmf(x_service, [6, 8, 10, 10])

tip_low    = fuzz.trapmf(x_tip, [0, 0, 5, 10])
tip_medium = fuzz.trapmf(x_tip, [8, 12, 18, 22])
tip_high   = fuzz.trapmf(x_tip, [18, 25, 30, 30])

# --- Ask user for inputs ---
fq = float(input("Enter food quality (0–10): "))
sq = float(input("Enter service quality (0–10): "))

# --- Membership values ---
rancid    = fuzz.interp_membership(x_food, food_rancid, fq)
fine      = fuzz.interp_membership(x_food, food_fine, fq)
delicious = fuzz.interp_membership(x_food, food_delicious, fq)

poor      = fuzz.interp_membership(x_service, service_poor, sq)
good      = fuzz.interp_membership(x_service, service_good, sq)
excellent = fuzz.interp_membership(x_service, service_excellent, sq)

# --- Simple fuzzy reasoning (max rule firing strength) ---
# Low tip if service is poor OR food is rancid
low_strength = max(poor, rancid)
# Medium tip if service is good OR food is fine
medium_strength = max(good, fine)
# High tip if service is excellent OR food is delicious
high_strength = max(excellent, delicious)

# Clip the membership functions
low_tip    = np.fmin(low_strength, tip_low)
medium_tip = np.fmin(medium_strength, tip_medium)
high_tip   = np.fmin(high_strength, tip_high)

# Aggregate all outputs
aggregated = np.fmax(low_tip, np.fmax(medium_tip, high_tip))

# Defuzzify → crisp value
tip_value = fuzz.defuzz(x_tip, aggregated, 'centroid')

print(f"\nSuggested tip: {tip_value:.2f}%")
