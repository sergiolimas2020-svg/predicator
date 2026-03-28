#!/usr/bin/env python3
"""
Calculate goal probability percentages for each team based on their statistics
"""
import json
import os

def calculate_goal_probabilities(gf, gc, pj, posicion):
    """
    Calculate goal probabilities based on team statistics
    gf: goals for
    gc: goals against  
    pj: partidos jugados (matches played)
    posicion: league position (1-20)
    """
    
    # Average goals per match
    goals_per_match = gf / pj if pj > 0 else 0
    goals_against_per_match = gc / pj if pj > 0 else 0
    
    # Position factor (better teams tend to score more)
    position_factor = (21 - posicion) / 20  # 1.0 for position 1, 0.05 for position 20
    
    # Expected goals for this team
    expected_gf = goals_per_match + (position_factor * 0.5)
    expected_ga = goals_against_per_match
    
    # Calculate probabilities
    # Over 1.5: Probability that team scores OR concedes 2+ goals per match
    # Using simple estimation based on average goals
    over_1_5 = min(95, max(30, (expected_gf + expected_ga) * 40))
    
    # Over 2.5: Probability of 3+ total goals
    over_2_5 = min(85, max(15, (expected_gf + expected_ga) * 30))
    
    # Over 3.5: Probability of 4+ total goals
    over_3_5 = min(75, max(5, (expected_gf + expected_ga) * 20))
    
    # BTTS: Both teams to score
    # More likely if both teams score reasonably
    btts = min(80, max(20, (goals_per_match * goals_against_per_match) * 15))
    
    # BTS: Similar to BTTS
    bts = btts
    
    return {
        'over_1_5': f"{over_1_5:.0f}%",
        'over_2_5': f"{over_2_5:.0f}%",
        'over_3_5': f"{over_3_5:.0f}%",
        'btts': f"{btts:.0f}%",
        'bts': f"{bts:.0f}%"
    }

def update_colombia_json_with_goals():
    """Update colombia_stats.json with calculated goal probabilities"""
    
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(workspace_root, 'static', 'colombia_stats.json')
    
    # Read current JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        colombia_data = json.load(f)
    
    # Update each team with calculated goals probabilities
    for team_name, team_data in colombia_data.items():
        pos = team_data['position']
        gf = pos['goles_favor']
        gc = pos['goles_contra']
        pj = pos['partidos']
        posicion = pos['posicion']
        
        # Calculate probabilities
        goal_probs = calculate_goal_probabilities(gf, gc, pj, posicion)
        
        # Update goals section
        team_data['goals'] = goal_probs
        
        print(f"✅ {team_name:20} - Over 1.5: {goal_probs['over_1_5']:>4} | Over 2.5: {goal_probs['over_2_5']:>4} | BTTS: {goal_probs['btts']:>4}")
    
    # Save updated JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(colombia_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n✅ Goal probabilities updated successfully!")
    print(f"📍 File: {json_path}")

if __name__ == "__main__":
    update_colombia_json_with_goals()
