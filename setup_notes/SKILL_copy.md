---
name: no-limit-2026-setup
description: Set up a No Limit 2026 participant. Takes their API key, prepares their team's remote build machine (SSH key, alias, optional Codex or Claude app connection) or this computer, and adds the starter kit once the variant is announced. Safe to run again; each step skips what is done, so a later run only adds the kit.
metadata:
  version: "2026-11-05.2"
---

# No Limit 2026 participant setup

Each step first checks whether its result exists, says so, and moves on. The machine and
apps never wait for the starter kit; a later run adds it. Work on the participant's own
computer; in a hosted sandbox with no path to it, say so and hand the commands over, the one
case where they type anything.

## Rules

- Never ask for or print a private key or a password. Public keys (`.pub`) are safe to print.
  `<key>` stands for the API key itself: it lives in the conversation and goes into commands
  as is. Fill in every placeholder.
- Invoking this skill authorizes the setup below. Say what each change does, then do it. Ask
  only for the facts named here. The participant types nothing in a terminal: run every
  command yourself and hand them only what needs their browser or the Codex or Claude
  app (copying their API key, the sign-in, the connection).
- A refused read or write is final: a sandbox denial, a declined approval, `Permission denied`
  or `Operation not permitted`. Never retry it, ask for the permission or hand the command
  over: take the step's fallback, or go on without that file and say so in step 7.
- Everything on the site goes through its API with `curl` (`curl.exe` in PowerShell): never
  open or drive a browser and never ask for the site address. `<site>` is
  `https://pokerbot.sequoiacap.com/tournament` and the API is under `<site>/api`. Link directly
  to anything they do on the site.
- Back up a file before editing it. Accept the machine's host key for the participant:
  `<ssh>`, `<scp>` and `<sftp>` (3b) carry `-o StrictHostKeyChecking=accept-new`, so no
  fingerprint prompt ever reaches them. Never turn that checking off (`no`, or a throwaway known-hosts
  file), never enable agent forwarding, and never copy a private key or the API key to the
  build machine.

## 1. API key

Already done when a key pasted earlier in this conversation, or one saved in
`~/.config/no-limit-2026/api-key` (Windows `$env:APPDATA\no-limit-2026\api-key`), passes:

```bash
curl -fsS -H "Authorization: Bearer <key>" <site>/api/auth/api-key
```

The answer lists `teams` (`team_id`, `team_name`, `competition_name`); `<team>` below is
this competition's `team_id`, and with several, ask which. No `teams` means the organizer
has not added them to a team yet: say so and end at step 7. A 401 means a wrong or expired
key: ask for a new one.

Otherwise ask the participant to paste their API key from **Settings → API keys**,
`<site>#settings/api-keys`, and check it the same way. Then keep a copy for later runs,
owner-only; when refused, skip it, the key works from the conversation:

```bash
mkdir -p ~/.config/no-limit-2026 && chmod 700 ~/.config/no-limit-2026
printf '%s\n' '<key>' > ~/.config/no-limit-2026/api-key
chmod 600 ~/.config/no-limit-2026/api-key
```

PowerShell: `New-Item -ItemType Directory -Force "$env:APPDATA\no-limit-2026"`, then
`Set-Content -Encoding ascii "$env:APPDATA\no-limit-2026\api-key" '<key>'`.

Then read the team's machine:

```bash
curl -fsS -H "Authorization: Bearer <key>" <site>/api/teams/<team>/machine
```

Keep `team.name`, `machine.host`, `keys` (each with `type` and `fingerprint`) and
`links.download`. A null `machine` or an empty `host` means no machine yet.

## 2. Remote or local

Already answered remote when the alias from 3b exists and names `machine.host`. Otherwise
ask once: **"Do you want to build and test on your team's remote build machine, set up like
the tournament's, or only on this computer?"** Recommend remote. Remote: steps 3, 4
and 5. Local: step 6. If the team has no machine yet, say so, do step 3a anyway so the key
is ready, and offer step 6 meanwhile.

## 3. Remote: SSH key, alias and login

**3a. Key.** Keys live in `~/.ssh` (`$env:USERPROFILE\.ssh` on Windows). When reading or
writing there is refused, use `.no-limit-2026` in the current folder instead, created with
mode 700 and a `.gitignore` holding `*`, with every path written out in full; `<keydir>` is
whichever applies. Already done when a fingerprint in `keys` matches a `.pub` in `<keydir>`
whose private half sits beside it (`ssh-keygen -lf FILE.pub` prints it).
Otherwise find a usable key there: types ed25519, rsa or ecdsa, never `-sk` or dsa, the
private half beside it, and no passphrase, which `ssh-keygen -y -P "" -f KEY` proves by
printing the public key. If there is none, generate one without asking:

```bash
mkdir -p -m 700 <keydir>
ssh-keygen -t ed25519 -N "" -f <keydir>/id_ed25519    # or -f <keydir>/no-limit-2026 if that path is taken
```

(PowerShell 5.1 drops empty arguments: write `-P '""'` and `-N '""'`.) Register the chosen
`.pub` file (the body is its one line; in PowerShell write the JSON to a file with
`Set-Content -Encoding ascii` and pass `-d "@file"`):

```bash
curl -fsS -X POST -H "Authorization: Bearer <key>" -H 'Content-Type: application/json' \
  -d "{\"key\":\"$(cat <keydir>/id_ed25519.pub)\"}" <site>/api/teams/<team>/machine/keys
```

On 201 or 200, confirm the fingerprint is in the answer's `keys`; on 409 or 422, see
Troubleshooting. The machine accepts a new key within about half a minute.

**3b. Alias.** The config file is `~/.ssh/config`; when writing it is refused, it is
`.no-limit-2026/config` (made as in 3a). `<ssh>`, `<scp>` and `<sftp>` below stand for
`ssh`, `scp` and `sftp` with `-o StrictHostKeyChecking=accept-new`, plus `-F` with that
path in the fallback.
Already done when `ssh -G no-limit-2026-build` (`-F` likewise) prints `hostname` followed
by `machine.host`, `identityfile` followed by the chosen key, and `stricthostkeychecking
accept-new`. Otherwise back up the file and append, replacing an earlier block between the
same markers (PowerShell: `Add-Content -Encoding ascii`; in `.no-limit-2026/config` add
`UserKnownHostsFile` with `.no-limit-2026/known_hosts` in full):

```text
# BEGIN no-limit-2026 managed host
Host no-limit-2026-build
  HostName <machine.host>
  User ubuntu
  Port 22
  IdentityFile <chosen key, in full>
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
  ForwardAgent no
  ServerAliveInterval 30
  ServerAliveCountMax 3
# END no-limit-2026 managed host
```

`accept-new` records the host key at the first login and refuses a changed one later.

**3c. Login.** Probe:

```bash
<ssh> -o BatchMode=yes -o ConnectTimeout=10 no-limit-2026-build 'whoami; hostname; cloud-init status --wait; ls -la ~/work'
```

- `Failed to add the host to the list of known hosts`: a refused write; carry on,
  `accept-new` covers later logins.
- `Permission denied (publickey)`: see Troubleshooting.
- `ubuntu`, `status: done` and a listing of `~/work`: continue.

## 4. Remote: connect an app (optional)

Already done when `<ssh> no-limit-2026-build 'test -d ~/.claude/remote'` succeeds (the
Claude app connected) or the machine's `codex login status` (4a.1) reports a sign-in: say
which. Otherwise offer to connect the Codex app (4a), the Claude app (4b) or both; recommend
the one the participant uses, skip if declined. Both apps read `~/.ssh/config`: with the
block in `.no-limit-2026/config`, give it to the participant to add there first.

**4a. Codex app.**

1. Check the CLI through the login shell the app uses:
   `<ssh> no-limit-2026-build 'bash -lc "command -v codex && codex login status"'`, expecting
   `/usr/bin/codex`.
2. If signed in, keep it: a machine has one Codex account, the last sign-in wins.
   Otherwise start the sign-in and relay what it prints:
   `<ssh> no-limit-2026-build 'bash -lc "nohup codex login --device-auth >~/codex-login.log 2>&1 &"'`,
   then seconds later `<ssh> no-limit-2026-build 'cat ~/codex-login.log'`. Give the
   participant the address and code for their browser, then check `codex login status`.
3. In the Codex app, **Settings > Connections**: the participant adds `no-limit-2026-build`
   and picks the project folder `~/work`, where the kit lands as `starter-kit`.

**4b. Claude app.** The Claude desktop app installs Claude Code on the machine itself and
uses the participant's own sign-in.

1. `<ssh> no-limit-2026-build 'mkdir -p ~/worktrees'`, then check the file transfer the app
   needs: `echo pwd | <sftp> -b - no-limit-2026-build` prints `Remote working directory`.
2. Note the recorded fingerprint: `ssh-keygen -l -F <machine.host>` (`-f` with
   `.no-limit-2026/known_hosts` in the fallback).
3. Hand over these clicks in the app's **Code** tab: the environment selector under the
   prompt box, **New environment**, **SSH**, then **Host** > **Add SSH connection…** with
   **Name** `No Limit 2026`, **SSH host** `no-limit-2026-build`, port and key empty,
   **Worktree folder** `~/worktrees`; **Add SSH connection**, folder `~/work`, **Create
   environment**. If it asks `Connect to … for the first time?`, the fingerprint must match
   before **Trust and connect**.

## 5. Remote: the starter kit on the machine

The kit appears when the variant is announced, at the start of the event. Already done when
`<ssh> no-limit-2026-build 'test -x ~/work/starter-kit/.venv/bin/poker-agent'` succeeds.
Otherwise:

1. Download the kit on this computer with the key, from `links.download` (step 1):
   `curl -fL -H "Authorization: Bearer <key>" -o starter-kit.zip <links.download>`. A 404
   means the variant is not announced yet: say the machine is ready and a run after the
   announcement adds the kit, then go to step 7.
2. `<scp> starter-kit.zip no-limit-2026-build:work/`, then
   `<ssh> no-limit-2026-build 'cd ~/work && unzip -qo starter-kit.zip'`.
3. On the machine (over `<ssh>`), in `~/work/starter-kit`, build the environment and run the
   smoke test:

   ```bash
   python3.12 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   .venv/bin/python -m pip install -e ./sdk/agent-protocol -e ./sdk/engine -e ./sdk/agent-sdk
   .venv/bin/poker-agent check agent.py
   .venv/bin/poker-agent play . examples/check_or_fold examples/min_raiser --tables 2 --no-history
   ```

   `check` must pass and `play` must print a summary with zero failed decisions.
4. Hand over: `ssh no-limit-2026-build` (with `-F` in the fallback), then
   `cd ~/work/starter-kit && source .venv/bin/activate`, and read the kit's `AGENTS.md` and
   `README.md` there.

## 6. Local: the starter kit on this computer

**6a. Prerequisites.** Check and report what is missing: Python 3.12 exactly
(`python3.12 --version`, Windows `py -3.12 --version`; never 3.13 or later, never changing
the system default), `python3.12 -m ensurepip --version` (Debian and Ubuntu need
`python3.12-venv`), `curl` and `unzip` (`tar` on Windows). Offer to install what is missing.

**6b. Kit.** The kit folder is the current folder, `./starter-kit`, or a folder the
participant names, when it holds `README.md`, `requirements.txt` and `sdk/`. Without one,
offer to download it as in step 5.1 and unpack it with `unzip -q starter-kit.zip`
(`tar -xf starter-kit.zip` on Windows). On a 404, skip 6c: a later run adds the kit.

**6c. Environment.** Already done when the kit folder's `.venv/bin/poker-agent` (Windows
`.venv\Scripts\poker-agent.exe`) exists. Otherwise offer step 5.3's commands in the kit
folder (`py -3.12` makes the venv on Windows). On native Windows use
`.venv\Scripts\` and run only `check`: the simulator needs WSL or the machine. Read the
kit's `AGENTS.md`.

## 7. Finish

Report in a few lines: the key (saved, or kept in the conversation), remote or local, the
SSH key (fingerprint, fallback folder if used), the login, the apps (what you saw versus
what they reported), the prerequisites and the kit (where, smoke test result, or waiting for
the announcement). For each open issue give the step, the evidence and the smallest next
action. Without the kit, say to run the skill again after the announcement
(`$no-limit-2026-setup` in Codex, `/no-limit-2026-setup` in Claude Code). End with this line:

```text
Skill version 2026-11-05.2, re-download from <site>/no-limit-2026-setup/SKILL.md
```

## Troubleshooting

| Symptom | Meaning and action |
| --- | --- |
| API answers 401 | The key is wrong or expired. New key at `<site>#settings/api-keys`, then step 1. |

| Registering answers 409 or 422 | Five keys already (the participant removes one at `<site>#settings/ssh-keys`) or a refused type (use ed25519). |
| `Permission denied (publickey)` | Step 3c: wait half a minute, then check `IdentityFile`, the fingerprint in `keys`, no passphrase, mode 600. |
| `Host key verification failed` | The machine's host key changed since it was first accepted: stop and ask the organizers. |
| `Connection timed out` or `refused` | Outbound port 22 blocked (VPN or firewall), or the machine is stopped: ask the organizers. |
| `codex` or `python3.12` not found over SSH | First boot still installing: wait for `cloud-init status --wait`. |
| Device sign-in refused | The ChatGPT workspace forbids device codes: ask its admin, or use the Claude app. |
| Claude app has no **SSH** tab or cannot connect | Update the app, recheck 4b.1; its `ssh.log` shows the failing step. |
