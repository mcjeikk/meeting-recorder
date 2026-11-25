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
        Caption { text: "Transcripciones"; font.pixelSize: 24 }
        ActionButton {
            objectName: "importButton"
            text: "Transcribir archivo…"
            enabled: library.available
            onClicked: desk.importFiles()
        }
        Caption {
            Layout.fillWidth: true
            secondary: true
            text: library.available ? "También puedes soltar un archivo de audio o video aquí."
                                    : "Instala el motor de transcripción para importar un archivo."
        }
        Caption { visible: library.importStatus.length > 0; Layout.fillWidth: true; text: library.importStatus }
        Caption { visible: library.summary.length > 0; Layout.fillWidth: true; text: library.summary; secondary: true }
        Caption { visible: library.rows.length === 0; text: "Aún no hay transcripciones."; secondary: true }
        ColumnLayout {
            objectName: "jobList"
            Layout.fillWidth: true
            spacing: 4
            Repeater {
                model: library.rows
                delegate: Button {
                    id: row
                    required property var modelData
                    Layout.fillWidth: true
                    leftPadding: 12
                    rightPadding: 12
                    implicitHeight: Math.max(40, contentItem.implicitHeight + 14)
                    text: modelData.label
                    onClicked: library.select(modelData.id)
                    background: Rectangle {
                        radius: 6
                        color: row.hovered ? Theme.hover : Theme.surface
                        border.color: row.visualFocus || library.detail.id === row.modelData.id ? Theme.accent : Theme.line
                    }
                    contentItem: Text {
                        text: row.text
                        color: Theme.text
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }
        }
        Caption { visible: library.detail.id.length > 0; text: library.detail.status; Layout.fillWidth: true }
        Caption { visible: library.detail.info.length > 0; secondary: true; text: library.detail.info; Layout.fillWidth: true }
        ProgressBar {
            Layout.fillWidth: true
            from: 0
            to: 100
            value: library.detail.progress
            indeterminate: visible && value <= 0
            visible: ["pending", "extracting", "running"].includes(library.detail.state)
            Accessible.name: "Progreso de transcripción"
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            ActionButton {
                objectName: "resultButton"
                text: "Abrir resultado"
                visible: library.detail.state === "done" && library.detail.result.length > 0
                onClicked: library.openResult()
            }
            ActionButton {
                objectName: "logButton"
                text: "Ver registro"
                visible: library.detail.log.length > 0
                onClicked: library.openLog()
            }
            ActionButton { text: "Reintentar"; visible: library.detail.state === "error"; onClicked: library.retry() }
            ActionButton {
                text: "Cancelar"
                visible: ["pending", "extracting", "running"].includes(library.detail.state)
                onClicked: library.cancel()
            }
            ActionButton { text: "Limpiar fallidos"; visible: library.detail.clearable; onClicked: library.clearFailed() }
        }
    }
}
