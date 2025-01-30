import subprocess
import re
from datetime import datetime

# --- CONFIGURATIONS ---
MAX_GAP_MINUTES = 90  # If commits are within 90 minutes, assume they belong to the same 'coding session'
TIME_PER_LINE_MINUTES = 0.02  # Rough estimate: 1 line might take ~1.2 seconds (0.02 minutes)
PRE_COMMIT_LINE_FACTOR = 1  # This is purely a heuristic, adjust as you see fit. 1 guestimates the time based on all lines changed since the last commit.

def get_git_commit_data():
    """
    Returns a list of commit info:
    [
        {
          'timestamp': datetime object,
          'hash': 'abc123',
          'lines_changed': int
        },
        ...
    ]
    """
    # Command to get commits in chronological order (oldest first),
    # along with lines added/removed in each commit
    # %ct = commit timestamp (unix epoch), %H = commit hash
    # --numstat prints lines added and removed for each file
    cmd = ['git', 'log', '--reverse', '--pretty=format:%ct %H', '--numstat']
    
    # Run the command and capture the output
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    lines = result.stdout.strip().split('\n')
    
    commits = []
    current_commit = None
    
    time_hash_pattern = re.compile(r'^(\d+)\s+([0-9a-f]+)$')  # e.g. 1675076488 abc123
    
    for line in lines:
        # Check if line matches the commit line
        match = time_hash_pattern.match(line)
        if match:
            # Start a new commit record
            epoch_str, commit_hash = match.groups()
            epoch = int(epoch_str)
            current_commit = {
                'timestamp': datetime.fromtimestamp(epoch),
                'hash': commit_hash,
                'lines_changed': 0
            }
            commits.append(current_commit)
        
        else:
            # If it doesn't match, it might be a file diff line e.g. "4   2   path/to/file"
            diff_parts = line.strip().split('\t')
            if len(diff_parts) == 3 and current_commit:
                added_str, removed_str, _ = diff_parts
                # Sometimes added or removed can be '-' (binary files). Handle that.
                try:
                    added = int(added_str) if added_str.isdigit() else 0
                    removed = int(removed_str) if removed_str.isdigit() else 0
                except ValueError:
                    added, removed = 0, 0
                
                current_commit['lines_changed'] += (added + removed)
    
    return commits

def group_commits_into_sessions(commits):
    """
    Group commits into sessions if the time gap between consecutive commits
    is less than MAX_GAP_MINUTES.
    
    Returns a list of sessions, each session is a list of commit dicts.
    """
    sessions = []
    current_session = []
    
    for i, commit in enumerate(commits):
        if i == 0:
            current_session.append(commit)
            continue
        
        prev_commit = commits[i-1]
        time_diff = (commit['timestamp'] - prev_commit['timestamp']).total_seconds() / 60.0
        
        if time_diff <= MAX_GAP_MINUTES:
            # Same session
            current_session.append(commit)
        else:
            # New session
            sessions.append(current_session)
            current_session = [commit]
    
    # Append the last session
    if current_session:
        sessions.append(current_session)
    
    return sessions

def estimate_session_time(session):
    """
    Estimate total coding time for a single session.
    1. Calculate the direct time from first to last commit.
    2. Add a 'pre-commit buffer' for lines changed in the first commit of the session.
    """
    if not session:
        return 0
    
    start_time = session[0]['timestamp']
    end_time = session[-1]['timestamp']
    direct_time_minutes = (end_time - start_time).total_seconds() / 60.0
    
    # Heuristic: lines from the first commit might represent time spent before the first commit
    first_commit_lines = session[0]['lines_changed']
    pre_commit_estimate = first_commit_lines * TIME_PER_LINE_MINUTES * PRE_COMMIT_LINE_FACTOR
    
    return direct_time_minutes + pre_commit_estimate

def main():
    print("Gathering commit data...")
    commits = get_git_commit_data()
    if not commits:
        print("No commit data found.")
        return
    
    print(f"Found {len(commits)} commits.")
    sessions = group_commits_into_sessions(commits)
    print(f"Grouped into {len(sessions)} sessions.")
    
    total_minutes = 0
    for i, session in enumerate(sessions, start=1):
        session_time = estimate_session_time(session)
        total_minutes += session_time
        print(f"Session {i}: {len(session)} commits, ~{session_time:.1f} minutes estimated")
    
    print("\n--- Summary ---")
    hours = total_minutes / 60.0
    print(f"Total Estimated Coding Time: ~{hours:.1f} hours")

if __name__ == "__main__":
    main()
