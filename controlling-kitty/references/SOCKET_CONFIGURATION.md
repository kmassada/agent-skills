# Kitty Remote Control & Socket Configuration

This guide details how to configure and authenticate Kitty's remote-control
protocol (`kitty @`) for seamless agent orchestration.

---

## 1. Remote Control Security Model

Kitty disables remote control by default, and for good reason: anything that can
reach `kitty @` can run `launch` (arbitrary code execution as you) and
`get-text` (read every window's scrollback). Treat the socket as a credential.

### Recommended Configuration (`kitty.conf`)

```conf
# Accept remote control ONLY over the socket below, never from programs
# that merely happen to be running inside a kitty window.
allow_remote_control socket-only

# Keep the socket in a private, per-user runtime directory - not /tmp.
listen_on unix:${XDG_RUNTIME_DIR}/kitty-%p

# Require a shared secret for every remote-control command.
remote_control_password "<your-password>"
```

Why each line matters:

* **`socket-only` rather than `yes`.** With `allow_remote_control yes`, *any*
  program that can write to the terminal can drive kitty - including a process
  on the far end of an SSH session, which can emit the control sequences
  remotely. `socket-only` restricts control to holders of the socket path.
* **Runtime directory rather than `/tmp`.** `/tmp` is world-traversable and
  shared between users on multi-user hosts. A fixed name such as
  `unix:/tmp/kitty-agent` is also predictable, so another local user can squat
  the path before kitty claims it. `%p` (the PID) keeps the name unique per
  instance. On macOS there is no `XDG_RUNTIME_DIR` by default; use the
  per-user `unix:$TMPDIR/kitty-%p`, which is already private.
* **`remote_control_password`.** Anyone who can open the socket otherwise has
  full control. The password can be scoped to specific commands, for example
  read-only observation:

  ```conf
  remote_control_password "observer-secret" get-text ls
  ```

> [!WARNING]
> `allow_remote_control yes` combined with a socket in `/tmp` gives every local
> user on the machine the ability to execute commands as you and to read your
> scrollback. Use it only on a single-user machine you trust, and prefer the
> configuration above.

---

## 2. Environment Variables & Socket Discovery

When Kitty runs with `listen_on`, child processes automatically inherit:

* `KITTY_LISTEN_ON`: The UNIX socket path (e.g.,
  `unix:/run/user/1000/kitty-12345`).
* `KITTY_WINDOW_ID`: The unique integer ID of the current Kitty window.
* `KITTY_PID`: Process ID of the parent Kitty instance.

### Interacting from Outside Kitty (IDE subshells or CI)

If the agent is running in an external subshell (such as the Antigravity IDE
terminal, VS Code terminal, or background process), `$KITTY_LISTEN_ON` will not
be automatically present in the subshell environment.

Pass the target socket explicitly using the `--to` flag:

```bash
kitty @ --to "$KITTY_SOCKET" ls
kitty @ --to "$KITTY_SOCKET" launch --type=tab --keep-focus agy
```

Or export the environment variable:

```bash
export KITTY_LISTEN_ON="$KITTY_SOCKET"
```

If you set `remote_control_password`, hand the password to `kitty @` out of
band rather than on the command line:

```bash
# From a file. Bare --password-file defaults to `rc-pass` in the kitty
# config directory; relative paths resolve from there.
kitty @ --to "$KITTY_SOCKET" --password-file ls

# Or from the environment. Bare --password-env defaults to KITTY_RC_PASSWORD.
KITTY_RC_PASSWORD="$(pass show kitty/rc)" \
  kitty @ --to "$KITTY_SOCKET" --password-env ls
```

> [!WARNING]
> Do not use `--password <secret>`. A literal password in `argv` is visible in
> `ps` output to every other process on the machine, and is recorded in shell
> history. Use `--password-file` or `--password-env` instead.

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
2. `kitty.conf` contains `allow_remote_control socket-only` (or `yes`) and a
   matching `listen_on` line.
3. You restarted Kitty after editing `kitty.conf`, or launched it with an
   explicit override:

   ```bash
   kitty -o allow_remote_control=socket-only \
     --listen-on "unix:${XDG_RUNTIME_DIR:-$TMPDIR}/mykitty"
   ```

4. The socket path you passed to `--to` matches the one Kitty is listening on;
   `%p` expands to the Kitty PID, so the name differs per instance.
