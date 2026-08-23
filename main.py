from datetime import date
import calendar
import webbrowser
import urllib.parse

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.checkbox import CheckBox
from kivy.factory import Factory

import database

DAYS = [str(d) for d in range(1, 32)]
MONTHS = list(calendar.month_name)[1:]
CURRENT_YEAR = date.today().year
YEARS = [str(y) for y in range(CURRENT_YEAR, CURRENT_YEAR + 5)]

TIMES = []
for hour in range(8, 23):
    for minute in (0, 30):
        TIMES.append(f"{hour:02d}:{minute:02d}")


class RootWidget(FloatLayout):
    pass


class FestivalApp(App):
    def build(self):
        database.init_db()

        root = RootWidget()

        list_container = BoxLayout(orientation="vertical", padding=dp(15), spacing=dp(10))

        heading = Factory.StyledLabel(
            text="Beer Festival List",
            font_size="24sp",
            bold=True,
            halign="center",
            size_hint_y=None,
            height=dp(44),
        )
        heading.bind(size=heading.setter("text_size"))
        list_container.add_widget(heading)

        self.list_layout = GridLayout(cols=1, size_hint_y=None, spacing=dp(8))
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))

        scroll = ScrollView()
        scroll.add_widget(self.list_layout)
        list_container.add_widget(scroll)

        root.add_widget(list_container)

        add_button = Factory.FloatingAddButton(
            text="+",
            size_hint=(None, None),
            size=(dp(64), dp(64)),
            pos_hint={"right": 0.95, "y": 0.04},
        )
        add_button.bind(on_press=self.open_add_popup)
        root.add_widget(add_button)

        self.refresh_list()

        return root

    def open_add_popup(self, instance):
        popup_layout = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))

        form = GridLayout(cols=2, spacing=dp(8), padding=dp(10), size_hint_y=None, height=dp(380))

        form.add_widget(Factory.StyledLabel(text="Name:"))
        self.name_input = Factory.StyledTextInput(multiline=False)
        form.add_widget(self.name_input)

        form.add_widget(Factory.StyledLabel(text="Location / Address:"))
        self.location_input = Factory.StyledTextInput(multiline=False)
        form.add_widget(self.location_input)

        form.add_widget(Factory.StyledLabel(text="Start date:"))
        start_row = BoxLayout(spacing=dp(5))
        self.start_day = Spinner(text=DAYS[0], values=DAYS)
        self.start_month = Spinner(text=MONTHS[0], values=MONTHS)
        self.start_year = Spinner(text=YEARS[0], values=YEARS)
        start_row.add_widget(self.start_day)
        start_row.add_widget(self.start_month)
        start_row.add_widget(self.start_year)
        form.add_widget(start_row)

        form.add_widget(Factory.StyledLabel(text="One day only:"))
        self.one_day_checkbox = CheckBox(size_hint=(None, None), size=(dp(30), dp(30)))
        self.one_day_checkbox.bind(active=self.toggle_one_day)
        checkbox_row = BoxLayout()
        checkbox_row.add_widget(self.one_day_checkbox)
        form.add_widget(checkbox_row)

        form.add_widget(Factory.StyledLabel(text="End date:"))
        end_row = BoxLayout(spacing=dp(5))
        self.end_day = Spinner(text=DAYS[0], values=DAYS)
        self.end_month = Spinner(text=MONTHS[0], values=MONTHS)
        self.end_year = Spinner(text=YEARS[0], values=YEARS)
        end_row.add_widget(self.end_day)
        end_row.add_widget(self.end_month)
        end_row.add_widget(self.end_year)
        form.add_widget(end_row)

        form.add_widget(Factory.StyledLabel(text="Opening time:"))
        self.time_spinner = Spinner(text=TIMES[0], values=TIMES)
        form.add_widget(self.time_spinner)

        popup_layout.add_widget(form)

        button_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        cancel_button = Factory.CancelButton(text="Cancel")
        button_row.add_widget(cancel_button)

        save_button = Factory.RoundedButton(text="Save Festival")
        button_row.add_widget(save_button)

        popup_layout.add_widget(button_row)

        self.popup = Popup(
            title="Add Festival",
            content=popup_layout,
            size_hint=(0.9, 0.8),
        )
        save_button.bind(on_press=self.add_festival)
        cancel_button.bind(on_press=self.popup.dismiss)

        self.popup.open()

    def toggle_one_day(self, checkbox, is_active):
        self.end_day.disabled = is_active
        self.end_month.disabled = is_active
        self.end_year.disabled = is_active

    def add_festival(self, instance):
        name = self.name_input.text.strip()
        location = self.location_input.text.strip()

        if not name:
            return

        try:
            start_date = date(
                int(self.start_year.text),
                MONTHS.index(self.start_month.text) + 1,
                int(self.start_day.text),
            )
            if self.one_day_checkbox.active:
                end_date = start_date
            else:
                end_date = date(
                    int(self.end_year.text),
                    MONTHS.index(self.end_month.text) + 1,
                    int(self.end_day.text),
                )
        except ValueError:
            return

        if end_date < start_date:
            return

        opening_time = self.time_spinner.text

        database.add_festival(name, location, start_date, end_date, opening_time)

        self.refresh_list()
        self.popup.dismiss()

    def open_in_maps(self, location_text):
        query = urllib.parse.quote(location_text)
        url = f"https://www.google.com/maps/search/?api=1&query={query}"
        webbrowser.open(url)

    def refresh_list(self):
        self.list_layout.clear_widgets()
        festivals = database.get_all_festivals()
        for festival in festivals:
            card = Factory.FestivalCard(orientation="horizontal")

            # --- Left column: date range + opening time ---
            date_column = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(190))

            date_range_text = (
                f"{festival['start_date'].strftime('%a %d %b %Y')} to "
                f"{festival['end_date'].strftime('%a %d %b %Y')}"
            )
            date_label = Factory.StyledLabel(
                text=date_range_text,
                font_size="13sp",
                bold=True,
                halign="left",
                valign="middle",
                size_hint_y=0.5,
            )
            date_label.bind(size=date_label.setter("text_size"))
            date_column.add_widget(date_label)

            time_label = Factory.StyledLabel(
                text=f"{festival['opening_time']} opening",
                font_size="13sp",
                halign="left",
                valign="middle",
                size_hint_y=0.5,
            )
            time_label.bind(size=time_label.setter("text_size"))
            date_column.add_widget(time_label)

            card.add_widget(date_column)

            # --- Middle column: name + address ---
            details = BoxLayout(orientation="vertical")

            name_label = Factory.StyledLabel(
                text=festival["name"],
                font_size="18sp",
                bold=True,
                halign="center",
                valign="middle",
                size_hint_y=0.5,
            )
            name_label.bind(size=name_label.setter("text_size"))
            details.add_widget(name_label)

            location_label = Factory.StyledLabel(
                text=festival["location"],
                font_size="13sp",
                halign="center",
                valign="middle",
                size_hint_y=0.5,
            )
            location_label.bind(size=location_label.setter("text_size"))
            details.add_widget(location_label)

            card.add_widget(details)

            # --- Right column: Google Maps button ---
            maps_button = Factory.RoundedButton(
                text="Location on\nGoogle Maps",
                font_size="12sp",
                halign="center",
                size_hint_x=None,
                width=dp(110),
            )
            maps_button.bind(
                on_press=lambda instance, loc=festival["location"]: self.open_in_maps(loc)
            )
            card.add_widget(maps_button)

            self.list_layout.add_widget(card)


if __name__ == "__main__":
    FestivalApp().run()
