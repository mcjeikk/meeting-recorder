import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ScrollView {
    id: scroll
    clip: true
    contentWidth: availableWidth
    contentHeight: body.implicitHeight + 32
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ColumnLayout {
        id: body
        x: 16
        y: 15
        width: scroll.availableWidth - 32
        spacing: 10
        Caption { text: "Ajustes"; font.pixelSize: 24 }
        Caption { text: "Carpeta de salida" }
        Caption { secondary: true; text: prefs.values.output_dir; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
        ActionButton { text: "Elegir carpeta…"; onClicked: desk.chooseOutput() }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
        Caption { text: "Transcripción"; font.pixelSize: 18 }
        Repeater {
            model: [
                {key: "transcription_preset", label: "Velocidad y calidad"},
                {key: "transcription_pc_impact", label: "Uso del equipo"},
                {key: "transcription_language", label: "Idioma"},
                {key: "transcription_num_speakers", label: "Hablantes"}
            ]
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 4
                Caption { text: modelData.label; secondary: true }
                Choice {
                    objectName: modelData.key
                    Layout.fillWidth: true
                    caption: modelData.label
                    model: prefs.choices[modelData.key]
                    currentIndex: prefs.values[modelData.key]
                    onActivated: index => prefs.choose(modelData.key, index)
                }
                Caption {
                    Layout.fillWidth: true
                    secondary: true
                    visible: text.length > 0
                    text: modelData.key === "transcription_preset" ? prefs.values.presetHint
                          : modelData.key === "transcription_pc_impact" ? prefs.values.impactHint : ""
                }
            }
        }
        ActionButton { visible: desk.platformMac; text: "Motor y acceso a modelos…"; onClicked: desk.showEngine() }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.line }
        Caption { text: "Captura y audio"; font.pixelSize: 18 }
        Toggle {
            objectName: "hideSelf"
            text: "Excluir esta ventana de la captura"
            checked: prefs.values.exclude_window_from_capture
            onClicked: prefs.flag("exclude_window_from_capture", checked)
        }
        Toggle {
            text: "Reducir eco del micrófono"
            checked: prefs.values.reduce_echo
            onClicked: prefs.flag("reduce_echo", checked)
        }
        Toggle {
            Layout.fillWidth: true
            visible: !desk.platformMac
            text: "Silenciar el micrófono fuera de las llamadas"
            checked: prefs.values.auto_mute_follow_meeting
            onClicked: prefs.flag("auto_mute_follow_meeting", checked)
        }
        Caption { visible: inputs.routeHint.length > 0; Layout.fillWidth: true; secondary: true; text: inputs.routeHint }
        ActionButton { text: "Actualizar micrófonos"; enabled: !inputs.busy && !session.busy; onClicked: inputs.refresh() }
    }
}
