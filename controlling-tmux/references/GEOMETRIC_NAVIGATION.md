# Geometric Relative Pane Navigation

This reference document explains the geometric pane navigation workflow and math
for moving focus between adjacent tmux panes (`left`, `right`, `above`,
`under`).

## Preferred Automated Method

Use the helper script `{skill_dir}/scripts/relative_pane.py` to calculate
coordinates and select the adjacent pane automatically:

```bash
# Select pane to the right of the current agent session ($TMUX_PANE)
python3 {skill_dir}/scripts/relative_pane.py --direction=right --select

# Get the target pane ID without selecting it
python3 {skill_dir}/scripts/relative_pane.py --direction=under
```

## Manual Geometric Calculation Protocol (Fallback)

If the script is unavailable, execute these steps manually:

1. **Get Origin Pane ID:** Run `echo $TMUX_PANE` or
   `tmux display-message -p  '#{pane_id}'`.
2. **List Panes with Geometry:**

   ```bash
   tmux list-panes -F "#{pane_id} #{pane_left} #{pane_top} #{pane_right} #{pane_bottom}"
   ```

3. **Parse Bounding Boxes:** Locate the line matching the origin pane ID (e.g.
   `left:0, top:0, right:80, bottom:40`).

4. **Identify Adjacent Target:**

   - **Right:** `pane_left` $\ge$ origin `pane_right`, with vertical range
     overlap.
   - **Left:** `pane_right` $\le$ origin `pane_left`, with vertical range
     overlap.
   - **Under:** `pane_top` $\ge$ origin `pane_bottom`, with horizontal range
     overlap.
   - **Above:** `pane_bottom` $\le$ origin `pane_top`, with horizontal range
     overlap.

5. **Select Target Pane:**

   ```bash
   tmux select-pane -t <target_pane_id>
   ```
