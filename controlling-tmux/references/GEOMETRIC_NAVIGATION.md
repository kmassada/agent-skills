# Geometric Relative Pane Navigation

This reference document explains the geometric pane navigation workflow and math
for moving focus between adjacent tmux panes (`left`, `right`, `above`,
`under`).

## Preferred Automated Method

Use the helper script `{skill_dir}/scripts/relative_pane.py` to calculate
coordinates and select the adjacent pane automatically:

```bash
# Select pane to the right of the current agent session ($TMUX_PANE)
python3 {skill_dir}/scripts/relative_pane.py --direction=right --pane="$TMUX_PANE" --select

# Get the target pane ID without selecting it
python3 {skill_dir}/scripts/relative_pane.py --direction=under --pane="$TMUX_PANE"
```

Always pass `--pane`. The script scopes `list-panes` to that pane's window; with
no origin, tmux answers for whichever window is currently active, so a pane in
any other window resolves against the wrong layout - or appears to have no
neighbours at all.

## Manual Geometric Calculation Protocol (Fallback)

If the script is unavailable, execute these steps manually:

1. **Get Origin Pane ID:** Run `echo "$TMUX_PANE"`. Fall back to
   `tmux display-message -p '#{pane_id}'` only if that is empty - it is
   focus-volatile and reports whichever pane is active right now.
2. **List Panes with Geometry:** always scope with `-t <origin_pane_id>`, or
   tmux reports the active window instead of the origin pane's window.

   ```bash
   tmux list-panes -t <origin_pane_id> \
     -F "#{pane_id} #{pane_left} #{pane_top} #{pane_right} #{pane_bottom}"
   ```

3. **Parse Bounding Boxes:** Locate the line matching the origin pane ID (e.g.
   `left:0, top:0, right:80, bottom:40`).

4. **Identify Adjacent Target:**

   - **Right:** `pane_left` >= origin `pane_right`, with vertical range
     overlap.
   - **Left:** `pane_right` <= origin `pane_left`, with vertical range
     overlap.
   - **Under:** `pane_top` >= origin `pane_bottom`, with horizontal range
     overlap.
   - **Above:** `pane_bottom` <= origin `pane_top`, with horizontal range
     overlap.

5. **Select Target Pane** - only when the user asked to move focus:

   ```bash
   tmux select-pane -t <target_pane_id>
   ```
