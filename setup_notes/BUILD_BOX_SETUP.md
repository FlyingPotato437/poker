# Build box setup checklist (No Limit 2026)

Status when this was written (Fri Nov 6 2026):
- SSH key already created on this Mac: ~/.ssh/id_ed25519 (private, never share) and ~/.ssh/id_ed25519.pub (public, safe to share).
- Fingerprint: SHA256:k2LJLy5wgP+v5Zs9w3Yv2G4PFlGWR5npVR2I/yZXD4c
- No ~/.ssh/config yet (no box address yet).
- Nothing was uploaded or registered. The portal steps below are yours.
- Full organizer instructions: setup_notes/SKILL_copy.md (the organizers' SKILL.md). It was NOT installed anywhere.

## Part A. Do now (portal, in your browser)

1. Open https://pokerbot.sequoiacap.com/tournament and sign in.
2. Add your PUBLIC key: Account settings -> SSH keys -> Add key. Paste the single line printed by this command (public key only):
   `cat ~/.ssh/id_ed25519.pub`
   It starts with `ssh-ed25519`. Never paste anything from the file without `.pub`. (Max 5 keys per team.)
3. Create an API key (only needed if you want the organizers' skill or kit download to work from the command line): Settings -> API keys (https://pokerbot.sequoiacap.com/tournament#settings/api-keys) -> create. Keep it secret; do not paste it into chat.
4. Wait about 30 seconds after adding the SSH key before trying to log in.

## Part B. When the Build box tab shows an address

Replace ADDRESS with the address from the team's Build box tab.

1. Test login (answer "yes" if it asks to trust the host the first time):
   `ssh ubuntu@ADDRESS`
2. Optional shortcut: add this to the end of ~/.ssh/config (create the file if missing; `nano ~/.ssh/config`):

```
Host no-limit-2026-build
  HostName ADDRESS
  User ubuntu
  IdentityFile ~/.ssh/id_ed25519
  IdentitiesOnly yes
  ServerAliveInterval 30
```
   Then `ssh no-limit-2026-build` works. If you see "Permission denied (publickey)": wait 30 s, check the key is in the portal. "Host key verification failed": stop and ask the organizers. "Timed out": VPN/firewall blocks port 22, or box not started; ask organizers.
3. On the box, sign Codex in (you do the sign-in in your own browser):
   `codex login --device-auth`
   It prints a web address and a code. Open the address in your browser and enter the code. Then check: `codex login status`. (A box has one Codex account; the last sign-in wins.)
4. Use tmux so work survives a dropped connection (if missing, `sudo apt install tmux`):
   `tmux new -s work`   (reattach later: `tmux attach -t work`; detach: press Ctrl-b then d)
5. Work in `~/work`. The kit appears at `~/work/starter-kit` once installed.

## Part C. The starter kit (after the variant is announced)

Needs your API key, so you run it yourself in your own terminal. Do not paste the key in chat.

```
read -s KEY            # paste the key (nothing shows), press Enter
curl -fL -H "Authorization: Bearer $KEY" -o starter-kit.zip "<links.download>"
unset KEY
```
`<links.download>` is the download link from your team's machine page / API (the skill gets it from `https://pokerbot.sequoiacap.com/tournament/api/teams/<team>/machine`). Easiest: download the kit from the portal in your browser if it offers a button. A 404 means not announced yet.

Then copy it to the box and unpack:
```
scp starter-kit.zip no-limit-2026-build:work/
ssh no-limit-2026-build 'cd ~/work && unzip -qo starter-kit.zip'
```
Then on the box, in ~/work/starter-kit (the skill's smoke test; this downloads and runs code from pip, see below):
```
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -e ./sdk/agent-protocol -e ./sdk/engine -e ./sdk/agent-sdk
.venv/bin/poker-agent check agent.py
.venv/bin/poker-agent play . examples/check_or_fold examples/min_raiser --tables 2 --no-history
```
Then read the kit's AGENTS.md and README.md.

Note: our repo's own AGENTS.md says to work offline with no pip install on THIS laptop. These pip steps are for the organizers' box only.

## What in the organizers' SKILL.md sends data or runs code (your call)

- It tells the assistant to take your API key into the chat and save it to ~/.config/no-limit-2026/api-key. We do NOT do this.
- It sends your API key to https://pokerbot.sequoiacap.com/tournament/api (check key, read team machine, download kit).
- It uploads your PUBLIC ssh key to that API (same as the portal button).
- It writes ~/.ssh/config with `StrictHostKeyChecking accept-new` (auto-trusts the box host key on first connection; refuses a changed one later).
- It starts `codex login --device-auth` on the box in the background (nohup) and reads a log.
- It downloads a zip kit, copies it to the box, unzips it, then runs pip install from the internet on the box and executes `poker-agent` (kit code).
- Optional: Claude app SSH connection (not needed).
- It says to ask about the key in chat and "run every command yourself" so the participant types nothing; our rules override that.
