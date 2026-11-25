import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ScrollView {
    id: scroll
    objectName: "recordingScroll"
    clip: true
    contentWidth: availableWidth
    contentHeight: body.implicitHeight + 26
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ColumnLayout {
        id: body
        x: 16
        y: 13
        width: scroll.availableWidth - 32
        spacing: 8
        Caption { text: "Grabación"; font.pixelSize: 24 }
        Caption { text: "Fuente de captura" }
        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Choice {
                id: source
                objectName: "sourcePicker"
                caption: "Fuente de captura"
                Layout.fillWidth: true
                Layout.minimumWidth: 60
                model: picker.labels
                currentIndex: picker.index
                enabled: session.phase === "idle" || session.phase === "recovery"
                onActivated: index => picker.select(index)
                Connections { target: source.popup; function onAboutToShow() { if (!desk.platformMac) picker.refresh() } }
            }
            ActionButton {
                objectName: "sourceRefresh"
                text: "Actualizar"
                enabled: source.enabled
                onClicked: desk.refreshSource()
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(163, Math.max(96, scroll.height * 0.245))
            color: "#101215"
            border.color: Theme.line
            radius: 8
            Image {
                anchors.fill: parent
                anchors.margins: 4
                source: previewImage.url
                fillMode: Image.PreserveAspectFit
                cache: false
            }
            Caption {
                anchors.centerIn: parent
                secondary: true
                text: "Sin vista previa"
                visible: previewImage.url.length === 0
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Caption { text: "Micrófono" }
            Item { Layout.fillWidth: true }
            Caption { secondary: true; text: desk.micUsage; elide: Text.ElideRight; Layout.maximumWidth: 167; maximumLineCount: 1 }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Choice {
                objectName: "micPicker"
                caption: "Micrófono"
                Layout.fillWidth: true
                Layout.minimumWidth: 60
                model: inputs.names
                currentIndex: inputs.index
                enabled: !session.busy && !inputs.busy
                onActivated: index => inputs.choose(index)
            }
            ActionButton {
                objectName: "muteButton"
                text: desk.metrics.muted ? "Activar mic." : "Silenciar"
                Accessible.name: desk.metrics.muted ? "Activar micrófono" : "Silenciar micrófono"
                onClicked: desk.toggleMute()
            }
        }
        Level { Layout.fillWidth: true; level: desk.metrics.mic }
        Toggle {
            objectName: "systemAudio"
            text: "Audio del sistema"
            checked: prefs.values.capture_system_audio
            enabled: session.phase === "idle"
            onClicked: prefs.flag("capture_system_audio", checked)
        }
        Level { Layout.fillWidth: true; level: desk.metrics.system }
        Toggle {
            objectName: "autoTranscribe"
            text: "Transcribir al terminar"
            enabled: library.available
            checked: enabled && prefs.values.transcribe_after_recording
            onClicked: prefs.flag("transcribe_after_recording", checked)
        }
        RowLayout {
            visible: desk.lastFile.length > 0
            Layout.fillWidth: true
            Caption { secondary: true; Layout.fillWidth: true; text: desk.lastFile }
            ActionButton { text: "Abrir carpeta"; onClicked: desk.openRecordingFolder() }
        }
    }
}
