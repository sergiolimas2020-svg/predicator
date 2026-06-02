#!/usr/bin/env python3
"""
Update footystats placeholders with reasonable default values
"""
import json
import os

def update_footystats():
    """Update footystats with reasonable defaults"""
    
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(workspace_root, 'static', 'colombia_stats.json')
    
    # Read current JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        colombia_data = json.load(f)
    
    # Update each team's footystats
    for team_name, team_data in colombia_data.items():
        goals = team_data['goals']
        
        # Use goals data as basis for footystats
        over_2_5 = goals['over_2_5']
        btts = goals['btts']
        
        team_data['footystats'] = {
            'over_2_5': over_2_5,
            'btts': btts
        }
    
    # Save updated JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(colombia_data, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Footystats updated successfully!")
    print(f"📍 File: {json_path}")

if __name__ == "__main__":
    update_footystats()
