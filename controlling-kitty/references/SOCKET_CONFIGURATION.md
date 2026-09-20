# Kitty Remote Control & Socket Configuration

This guide details how to configure and authenticate Kitty's remote-control
protocol (`kitty @`) for seamless agent orchestration.

---

## 1. Remote Control Security Model

For security, Kitty disables remote control by default. To allow AI agents to
interact with your Kitty terminal, configure remote control settings in your
`kitty.conf` configuration file (located at `~/.config/kitty/kitty.conf` on
macOS and Linux).

### Recommended Configuration (`kitty.conf`)

```conf
# Enable socket-based remote control
allow_remote_control yes

# Specify UNIX domain socket location (with %p PID substitution for uniqueness)
listen_on unix:/tmp/kitty-%p
```

Alternatively, to permit remote control only from specific authorized sockets
without allowing arbitrary subshell programs unfettered access:

```conf
allow_remote_control socket-only
listen_on unix:/tmp/kitty-agent
```

---

## 2. Environment Variables & Socket Discovery

When Kitty runs with `listen_on`, child processes automatically inherit:

* `KITTY_LISTEN_ON`: The UNIX socket path (e.g., `unix:/tmp/kitty-12345`).
* `KITTY_WINDOW_ID`: The unique integer ID of the current Kitty window.
* `KITTY_PID`: Process ID of the parent Kitty instance.

### Interacting from Outside Kitty (IDE subshells or CI)

If the agent is running in an external subshell (such as the Antigravity IDE
terminal, VS Code terminal, or background process), `$KITTY_LISTEN_ON` will not
be automatically present in the subshell environment.

Pass the target socket explicitly using the `--to` flag:

```bash
kitty @ --to unix:/tmp/kitty-agent ls
kitty @ --to unix:/tmp/kitty-agent launch --type=tab --keep-focus agy
```

Or export the environment variable:

```bash
export KITTY_LISTEN_ON=unix:/tmp/kitty-agent
```

---

## 3. Verifying Remote Control Connectivity

Run the following command to test if remote control is functioning properly:

```bash
kitty @ ls
```

If successful, Kitty returns a JSON array describing all active OS windows,
tabs, and windows.

If you encounter:

```text
kitty: Error: Could not connect to socket ...
```

Check that:

1. Kitty is running.
2. `kitty.conf` contains `allow_remote_control yes` (or `socket-only`).
3. You restarted Kitty or launched it with
   `kitty -o allow_remote_control=yes --listen-on unix:/tmp/mykitty`.
