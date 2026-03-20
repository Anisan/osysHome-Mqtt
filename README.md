# Mqtt - MQTT Protocol Integration

![Mqtt Icon](static/Mqtt.png)

MQTT protocol integration for connecting to MQTT brokers, subscribing to topics, and managing device communication.

## Description

The `Mqtt` module provides MQTT protocol integration for the osysHome platform. It enables connection to MQTT brokers, subscription to topics, bidirectional communication with devices, and automatic topic management.

## Main Features

- ✅ **MQTT Broker Connection**: Connect to MQTT brokers
- ✅ **Topic Management**: Create and manage MQTT topics
- ✅ **Bidirectional Communication**: Publish and subscribe to topics
- ✅ **Property Linking**: Link topics to object properties
- ✅ **Method Linking**: Link topics to object methods
- ✅ **Auto-Discovery**: Automatic topic discovery
- ✅ **Value Replacement**: Map values between MQTT and objects
- ✅ **Search Integration**: Search topics and linked objects

## Admin Panel

The module provides a comprehensive admin interface:

### Main View
- **Topics List**: View all configured topics
- **Connection Status**: Real-time connection status
- **Settings**: Configure broker connection

### Topic Configuration
- **Topic Path**: MQTT topic path
- **Title**: Display name
- **Linked Object**: Link to osysHome object
- **Linked Property**: Link to object property
- **Linked Method**: Link to object method
- **Value Replacement**: Map MQTT values to object values
- **QoS**: Quality of Service level
- **Retain**: Retain message flag
- **Read-only**: Read-only topic flag

## Connection Management

### Broker Settings
- **Host**: MQTT broker hostname/IP
- **Port**: MQTT broker port (default: 1883)
- **Login**: Username for authentication
- **Password**: Password for authentication
- **Auto-reconnect**: Automatic reconnection on disconnect

### Connection Status
- Real-time connection status display
- Reconnection attempts tracking
- Error message display
- WebSocket status updates

## Usage

### Configuring Broker

1. Navigate to Mqtt module
2. Enter broker host and port
3. Set authentication if required
4. Configure subscription topics
5. Save settings

### Creating Topic

1. Navigate to Mqtt module
2. Click "Add Topic"
3. Enter topic path
4. Link to object property or method
5. Configure value replacement if needed
6. Save topic

## Technical Details

- **MQTT Library**: paho-mqtt
- **Protocol Version**: MQTT 3.1.1
- **Threading**: Background connection management
- **WebSocket**: Real-time status updates
- **Value Mapping**: Bidirectional value transformation

## Version

Current version: **1.0**

## Category

Devices

## Actions

The module provides the following actions:
- `cycle` - Background connection management
- `search` - Search topics and linked objects

## Requirements

- Flask
- paho-mqtt
- SQLAlchemy
- osysHome core system

## Author

osysHome Team

## License

See the main osysHome project license

