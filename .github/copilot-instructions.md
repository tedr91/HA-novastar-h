# Novastar H Series Integration for Home Assistant

## Project Overview
This is a Home Assistant custom integration for Novastar H series LED video processors.

## Technical Details
- **Domain**: `novastar_h`
- **Protocol**: HTTP REST API
- **Platforms**: switch, select, number, media_player

## Development Guidelines
- Follow Home Assistant coding standards
- Use async/await for all I/O operations
- Test changes locally before committing
- Keep API client (`api.py`) separate from HA entity logic

## Workflow Preferences
- Do not commit, push, tag, create releases, or bump versions automatically
- Always pause after local edits/tests and wait for explicit user approval
- If the user says "publish", "publish it", or "let's publish", proceed with version bumping and publish steps

## File Structure
```
custom_components/novastar_h/
├── __init__.py          # Integration setup
├── api.py               # HTTP API client
├── config_flow.py       # Configuration flow
├── const.py             # Constants
├── coordinator.py       # Data update coordinator
├── manifest.json        # Integration manifest
├── media_player.py      # Media player entity
├── number.py            # Number entities (brightness)
├── select.py            # Select entities (presets)
├── strings.json         # UI strings
├── switch.py            # Switch entities (power, output)
└── translations/
    └── en.json          # English translations
```

## API Endpoints (Expected)
- `GET /api/status` - Device status
- `GET /api/device` - Device info
- `GET /api/presets` - List of presets
- `POST /api/power` - Set power state
- `POST /api/brightness` - Set brightness
- `POST /api/preset` - Set active preset
- `POST /api/output` - Enable/disable output
