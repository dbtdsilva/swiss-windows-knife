import QtQuick
import QtLocation
import QtPositioning

Item {
    id: root

    // Inputs from Python: current marker position. Bound, so re-assigning
    // these from Python moves the marker.
    property real markerLat: 0.0
    property real markerLng: 0.0

    // Emitted when the user taps the map. Python listens.
    signal coordinatesPicked(real lat, real lng)

    Plugin {
        id: osmPlugin
        name: "osm"
        PluginParameter {
            name: "osm.useragent"
            value: "swiss-windows-knife/1.0 (https://github.com/dbtdsilva/swiss-windows-knife)"
        }
    }

    Map {
        id: map
        anchors.fill: parent
        plugin: osmPlugin
        zoomLevel: 6
        copyrightsVisible: false

        // Centre the map once on creation; the user is then free to pan
        // without the centre being yanked back to the marker.
        Component.onCompleted: {
            center = QtPositioning.coordinate(root.markerLat, root.markerLng)
        }

        MapQuickItem {
            coordinate: QtPositioning.coordinate(root.markerLat, root.markerLng)
            anchorPoint.x: dot.width / 2
            anchorPoint.y: dot.height / 2
            sourceItem: Rectangle {
                id: dot
                width: 14
                height: 14
                radius: 7
                color: "#d33"
                border.color: "white"
                border.width: 2
            }
        }

        // TapHandler doesn't block the Map's own pan/pinch gestures.
        TapHandler {
            onTapped: function(eventPoint) {
                var coord = map.toCoordinate(eventPoint.position)
                root.markerLat = coord.latitude
                root.markerLng = coord.longitude
                root.coordinatesPicked(coord.latitude, coord.longitude)
            }
        }
    }
}
