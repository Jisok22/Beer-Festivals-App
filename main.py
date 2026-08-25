from datetime import date, timedelta
import calendar
import webbrowser
import urllib.parse

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
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

        list_container = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))

        heading = Factory.StyledLabel(
            text="Beer Festival Organiser",
            font_size="18sp",
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
            size=(dp(38.4), dp(38.4)),
            pos_hint={"right": 0.95, "top": 0.98},
        )
        add_button.bind(on_press=self.open_add_popup)
        root.add_widget(add_button)

        self.refresh_list()

        return root

    def open_add_popup(self, instance):
        popup_layout = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(5))

        form = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            padding=dp(10),
            size_hint_y=None,
            height=dp(380),
        )

        def add_form_row(label_text, field, row_size_hint_y=1):
            row = BoxLayout(spacing=dp(0), size_hint_y=row_size_hint_y)
            label = Factory.StyledLabel(text=label_text, font_size="13sp", size_hint_x=0.33)
            label.valign = "middle"
            label.bind(size=label.setter("text_size"))
            row.add_widget(label)
            field.size_hint = (0.67, 0.8)
            row.add_widget(field)
            form.add_widget(row)

        self.name_input = Factory.StyledTextInput(multiline=True)
        add_form_row("Name:", self.name_input)

        self.location_input = Factory.StyledTextInput(multiline=True)
        add_form_row("Location /\nAddress:", self.location_input)

        start_row = BoxLayout(spacing=dp(5))
        self.start_day = Spinner(text=DAYS[0], values=DAYS, font_size="11sp")
        self.start_month = Spinner(text=MONTHS[0], values=MONTHS, font_size="11sp")
        self.start_year = Spinner(text=YEARS[0], values=YEARS, font_size="11sp")
        start_row.add_widget(self.start_day)
        start_row.add_widget(self.start_month)
        start_row.add_widget(self.start_year)
        add_form_row("Start date:", start_row, row_size_hint_y=0.8)

        self.one_day_checkbox = CheckBox(size_hint=(None, None), size=(dp(30), dp(30)))
        self.one_day_checkbox.bind(active=self.toggle_one_day)
        checkbox_row = AnchorLayout(anchor_x="left", anchor_y="center")
        checkbox_row.add_widget(self.one_day_checkbox)
        add_form_row("One day only:", checkbox_row, row_size_hint_y=0.8)

        end_row = BoxLayout(spacing=dp(5))
        self.end_day = Spinner(text=DAYS[0], values=DAYS, font_size="11sp")
        self.end_month = Spinner(text=MONTHS[0], values=MONTHS, font_size="11sp")
        self.end_year = Spinner(text=YEARS[0], values=YEARS, font_size="11sp")
        end_row.add_widget(self.end_day)
        end_row.add_widget(self.end_month)
        end_row.add_widget(self.end_year)
        add_form_row("End date:", end_row, row_size_hint_y=0.8)

        self.start_day.bind(text=self.update_end_date)
        self.start_month.bind(text=self.update_end_date)
        self.start_year.bind(text=self.update_end_date)
        self.update_end_date()

        self.time_spinner = Spinner(text=TIMES[0], values=TIMES, font_size="11sp")
        add_form_row("Opening time:", self.time_spinner, row_size_hint_y=0.8)

        popup_layout.add_widget(form)

        button_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        cancel_button = Factory.CancelButton(text="Cancel", font_size="14sp")
        button_row.add_widget(cancel_button)

        save_button = Factory.RoundedButton(text="Save Festival", font_size="14sp")
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

    def update_end_date(self, *_):
        try:
            start_date = date(
                int(self.start_year.text),
                MONTHS.index(self.start_month.text) + 1,
                int(self.start_day.text),
            )
        except ValueError:
            return

        end_date = start_date + timedelta(days=1)
        if str(end_date.year) not in YEARS:
            return

        self.end_day.text = str(end_date.day)
        self.end_month.text = MONTHS[end_date.month - 1]
        self.end_year.text = str(end_date.year)

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
            card = Factory.FestivalCard(orientation="vertical", height=dp(100))

            top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(25))

            name_label = Factory.StyledLabel(text=festival["name"], font_size="15sp", bold=True)
            name_label.halign = "center"
            name_label.valign = "middle"
            name_label.bind(size=name_label.setter("text_size"))
            top_row.add_widget(name_label)
            card.add_widget(top_row)

            bottom_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56))

            # --- Bottom-left column: date range + opening time ---
            date_column = BoxLayout(orientation="vertical")

            date_range_text = (
                f"{festival['start_date'].strftime('%a %d %b %Y')} to "
                f"\n{festival['end_date'].strftime('%a %d %b %Y')}"
            )
            date_label = Factory.StyledLabel(
                text=date_range_text,
                font_size="10sp",
                bold=True,
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(36),
            )
            date_label.bind(size=date_label.setter("text_size"))
            date_column.add_widget(date_label)

            time_label = Factory.StyledLabel(
                text=f"Opens at {festival['opening_time']}",
                font_size="10sp",
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(20),
            )
            time_label.bind(size=time_label.setter("text_size"))
            date_column.add_widget(time_label)

            bottom_row.add_widget(date_column)

            # --- Bottom-middle column: wrapped address ---
            location_label = Factory.StyledLabel(
                text=festival["location"],
                font_size="10sp",
                halign="center",
                valign="middle",
                text_size=(0, None),
            )
            location_label.bind(width=lambda label, width: setattr(label, "text_size", (width, None)))
            location_label.bind(texture_size=lambda label, size: setattr(label, "height", size[1]))
            bottom_row.add_widget(location_label)

            # --- Bottom-right column: right-aligned Google Maps button ---
            maps_container = AnchorLayout(anchor_x="right", anchor_y="center")
            maps_button = Factory.RoundedButton(
                text="Google\nMaps",
                font_size="10sp",
                halign="center",
                size_hint_x=None,
                width=dp(56),
            )
            maps_button.bind(
                on_press=lambda instance, loc=festival["location"]: self.open_in_maps(loc)
            )
            maps_container.add_widget(maps_button)
            bottom_row.add_widget(maps_container)
            card.add_widget(bottom_row)

            self.list_layout.add_widget(card)


if __name__ == "__main__":
    FestivalApp().run()
