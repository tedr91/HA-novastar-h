# Novastar H Series Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for controlling Novastar H series LED video processors via their HTTP API.

## Features

- **Automatic Discovery**: Automatically finds Novastar processors on your network via SSDP/Zeroconf
- **Screen Output Control**: Fade to black (FTB) control for display output
- **Brightness Adjustment**: Control display brightness (0-100%)
- **Preset Selection**: Switch between configured presets
- **Media Player Entity**: Unified control interface with source selection

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → Custom repositories
3. Add `https://github.com/tedr91/HA-novastar-h` as an Integration
4. Search for "Novastar H Series" and install
5. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/novastar_h` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** and search for "Novastar H Series"
3. Enter the connection details:
   - **Host**: IP address of your Novastar processor
   - **Port**: API port (default: 8000)
   - **Project ID**: From Settings > OpenAPI Management on your device
   - **Secret Key**: From Settings > OpenAPI Management on your device
   - **Enable Encryption**: Optional DES encryption for API communication
   - **Name**: Display name for the device

### Getting Project ID and Secret Key

On your Novastar H series processor:
1. Go to **Settings** → **OpenAPI Management**
2. Add or view the access credentials
3. Copy the **pId** (Project ID) and **secretKey**

## Entities

After setup, the following entities will be available:

### Switches
- `switch.<name>_screen_output` - Screen output control (FTB/fade to black)

### Select
- `select.<name>_preset` - Preset selection

### Number
- `number.<name>_brightness` - Brightness control (0-100%)

### Media Player
- `media_player.<name>` - Unified control with source selection

## Supported Devices

This integration is designed for Novastar H series LED video processors, including:
- H2
- H5
- H9
- H15

## API Requirements

This integration communicates with the Novastar processor via the [Novastar OpenAPI](https://openapi.novastar.tech/en/h/doc-7540897). Ensure:
- The processor is connected to your network
- HTTP API access is enabled on the processor
- The configured port (default: 8000) is accessible
- You have obtained the Project ID and Secret Key from your device settings

### Encryption

The integration supports optional DES encryption for API communication. If enabled:
- The `pyDes` library is required (install via `pip install pyDes`)
- The first 8 bytes of your secret key are used as the encryption key

## Troubleshooting

### Cannot Connect
- Verify the IP address is correct
- Ensure the processor is powered on and connected to the network
- Check that no firewall is blocking port 8000
- Verify your Project ID and Secret Key are correct

### Entities Unavailable
- Check Home Assistant logs for error messages
- Verify the device is reachable on the network

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
