import tkinter as tk
from tkinter import ttk
import threading

class SlideSwitch(ttk.Frame):
    def __init__(self, parent, label, message_key, default_value=50, default_state=False, message_bus=None):
        super().__init__(parent)

        self.label_text = label
        self.message_key = message_key
        self.value = tk.IntVar(value=default_value)
        self.state = tk.BooleanVar(value=default_state)
        self.message_bus = message_bus

        self.slider_is_dragging = False
        self.slider_timer = None

        self._build_ui()

    def _build_ui(self):
        label = ttk.Label(self, text=self.label_text, font=("Segoe UI", 11, "bold"))
        label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(5, 0))

        self.slider = ttk.Scale(self, from_=0, to=100, orient="horizontal", variable=self.value,
                                command=self._on_slider_change)
        self.slider.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.columnconfigure(0, weight=1)

        self.toggle_button = ttk.Checkbutton(self, text="ON / OFF", variable=self.state,
                                             command=self._on_toggle)
        self.toggle_button.grid(row=1, column=1, padx=5, pady=5)

        self.status_label = ttk.Label(self, text=f"{self.value.get()}%", font=("Segoe UI", 10))
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="e", padx=5)

        self.slider.bind("<ButtonPress-1>", self._on_slider_start)
        self.slider.bind("<ButtonRelease-1>", self._on_slider_end)

    def _on_slider_start(self, event):
        self.slider_is_dragging = True

    def _on_slider_end(self, event):
        self.slider_is_dragging = False
        self._send_update()

    def _on_slider_change(self, value):
        val = int(float(value))
        self.status_label.config(text=f"{val}%")

        if not self.slider_is_dragging:
            self._send_update()

    def _on_toggle(self):
        self._send_update()

    def _send_update(self):
        payload = {
            "label": self.label_text,
            "key": self.message_key,
            "value": self.value.get(),
            "enabled": self.state.get()
        }
        if self.message_bus:
            self.message_bus.send("slider_switch_changed", payload)
        else:
            print("💡 変更通知:", payload)

    def get_state(self):
        return {
            "value": self.value.get(),
            "enabled": self.state.get()
        }

    def set_state(self, state_dict):
        if "value" in state_dict:
            self.value.set(state_dict["value"])
            self.status_label.config(text=f"{state_dict['value']}%")
        if "enabled" in state_dict:
            self.state.set(state_dict["enabled"])

# チE��ト用実行コーチE
if __name__ == "__main__":
    root = tk.Tk()
    root.title("SlideSwitch Demo")

    dummy_bus = type("DummyBus", (), {"send": lambda self, ev, data: print(f"[DummyBus] {ev} - {data}")})()

    frame = SlideSwitch(root, label="AI応答確玁E, message_key="ai_response_prob",
                        default_value=75, default_state=True, message_bus=dummy_bus)
    frame.pack(padx=20, pady=20, fill="x")

    root.mainloop()
