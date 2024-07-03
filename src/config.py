from mqtt.mqtt_as import config

local_config = {
    'ssid': 'Het Gemeentehuis',
    'wifi_pw': 'Garble',
    'server': 'homeassistant.local',
    'user': 'mqtt-user',
    'password': 'garble',
    'queue_len': 5
}

local_config = config | local_config
