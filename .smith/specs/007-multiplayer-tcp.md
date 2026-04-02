# Implement TCP/IP Multiplayer

## Priority: Low

## Description
Replace the stubbed DOS IPX networking in `MMULTI.C` with TCP/IP networking using BSD sockets (Linux) and Winsock (Windows).

## Requirements
- Server/client architecture (one host, up to 7 joiners)
- Command-line flags: `--host <port>` and `--join <ip:port>`
- Reliable packet delivery for game state sync
- Player movement prediction for latency tolerance
- Compatible with both Linux and Windows builds

## Files to modify
- `SRC/MMULTI.C` — replace stubs with socket networking
- `source/GAME.C` — add command-line parsing for network flags

## Testing
- Two instances can connect and see each other
- Player movement syncs correctly
- Graceful disconnect handling
