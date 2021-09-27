from typing import Any, Callable, Optional

import webviz_core_components as wcc
from dash import ALL, Dash, Input, Output, State, callback_context, no_update
from dash.exceptions import PreventUpdate

from webviz_subsurface._models import InplaceVolumesModel

from ..utils.utils import create_range_string, update_relevant_components


# pylint: disable=too-many-statements,too-many-arguments
def selections_controllers(
    app: Dash, get_uuid: Callable, volumemodel: InplaceVolumesModel
) -> None:
    @app.callback(
        Output(get_uuid("selections"), "data"),
        Input({"id": get_uuid("selections"), "tab": ALL, "selector": ALL}, "value"),
        Input(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": ALL},
            "value",
        ),
        Input(
            {"id": get_uuid("selections"), "tab": "voldist", "settings": "Colorscale"},
            "colorscale",
        ),
        State(get_uuid("page-selected"), "data"),
        State(get_uuid("tabs"), "value"),
        State(get_uuid("selections"), "data"),
        State(get_uuid("initial-load-info"), "data"),
        State({"id": get_uuid("selections"), "tab": ALL, "selector": ALL}, "id"),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": ALL}, "id"
        ),
    )
    def _update_selections(
        selectors: list,
        filters: list,
        colorscale: str,
        selected_page: str,
        selected_tab: str,
        previous_selection: dict,
        initial_load: dict,
        selector_ids: list,
        filter_ids: list,
    ) -> dict:
        ctx = callback_context.triggered[0]
        if ctx["prop_id"] == ".":
            raise PreventUpdate

        if previous_selection is None:
            previous_selection = {}

        page_selections = {
            id_value["selector"]: values
            for id_value, values in zip(selector_ids, selectors)
            if id_value["tab"] == selected_tab
        }
        page_selections["filters"] = {
            id_value["selector"]: values
            for id_value, values in zip(filter_ids, filters)
            if id_value["tab"] == selected_tab
        }

        page_selections.update(Colorscale=colorscale)
        page_selections.update(ctx_clicked=ctx["prop_id"])

        # check if a page needs to be updated due to page refresh or
        # change in selections/filters
        if initial_load[selected_page]:
            page_selections.update(update=True)
        else:
            equal_list = []
            for selector, values in page_selections.items():
                if selector != "ctx_clicked":
                    equal_list.append(
                        values == previous_selection[selected_page][selector]
                    )
            page_selections.update(update=not all(equal_list))

        previous_selection[selected_page] = page_selections
        return previous_selection

    @app.callback(
        Output(get_uuid("initial-load-info"), "data"),
        Input(get_uuid("page-selected"), "data"),
        State(get_uuid("initial-load-info"), "data"),
    )
    def _store_initial_load_info(page_selected: str, initial_load: dict) -> dict:
        if initial_load is None:
            initial_load = {}
        initial_load[page_selected] = page_selected not in initial_load
        return initial_load

    @app.callback(
        Output(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": ALL},
            "disabled",
        ),
        Output(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": ALL}, "value"
        ),
        Output(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": ALL}, "options"
        ),
        Input(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": "Plot type"},
            "value",
        ),
        Input(get_uuid("page-selected"), "data"),
        Input(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": "Color by"},
            "value",
        ),
        State(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": ALL}, "value"
        ),
        State(
            {"id": get_uuid("selections"), "tab": "voldist", "selector": ALL}, "options"
        ),
        State({"id": get_uuid("selections"), "tab": "voldist", "selector": ALL}, "id"),
        State(get_uuid("selections"), "data"),
        State(get_uuid("tabs"), "value"),
    )
    # pylint: disable=too-many-locals
    def _plot_options(
        plot_type: str,
        selected_page: str,
        selected_color_by: list,
        selector_values: list,
        selector_options: list,
        selector_ids: list,
        previous_selection: Optional[dict],
        selected_tab: str,
    ) -> tuple:
        ctx = callback_context.triggered[0]
        if (
            selected_tab != "voldist"
            or ("Color by" in ctx["prop_id"] and plot_type not in ["box", "bar"])
            or previous_selection is None
        ):
            raise PreventUpdate

        initial_page_load = selected_page not in previous_selection
        selections: Any = {}
        if initial_page_load:
            selections = {
                id_value["selector"]: options[0]["value"]
                if id_value["selector"] in ["Plot type", "X Response"]
                else None
                for id_value, options in zip(selector_ids, selector_options)
            }
        else:
            selections = (
                previous_selection.get(selected_page)
                if "page-selected" in ctx["prop_id"]
                else {
                    id_value["selector"]: values
                    for id_value, values in zip(selector_ids, selector_values)
                }
            )

        selectors_disable_in_pages = {
            "Plot type": ["per_zr", "conv"],
            "Y Response": ["per_zr", "conv"],
            "X Response": [],
            "Color by": ["per_zr", "conv"],
            "Subplots": ["per_zr", "1p1t"],
        }

        settings = {}
        for selector, disable_in_pages in selectors_disable_in_pages.items():
            disable = selected_page in disable_in_pages  # type: ignore
            value = None if disable else selections.get(selector)

            settings[selector] = {
                "disable": disable,
                "value": value,
            }

        if settings["Plot type"]["value"] in ["distribution", "histogram"]:
            settings["Y Response"]["disable"] = True
            settings["Y Response"]["value"] = None

        # update dropdown options based on plot type
        if settings["Plot type"]["value"] == "scatter":
            y_elm = x_elm = (
                volumemodel.responses + volumemodel.selectors + volumemodel.parameters
            )
        elif settings["Plot type"]["value"] in ["box", "bar"]:
            y_elm = x_elm = volumemodel.responses + volumemodel.selectors
            if selections.get("Y Response") is None:
                settings["Y Response"]["value"] = selected_color_by
        else:
            y_elm = volumemodel.selectors
            x_elm = volumemodel.responses

        colorby_elm = (
            list(volumemodel.dataframe.columns) + volumemodel.parameters
            if settings["Plot type"]["value"] == "scatter"
            else volumemodel.selectors
        )
        settings["Y Response"]["options"] = [
            {"label": elm, "value": elm} for elm in y_elm
        ]
        settings["X Response"]["options"] = [
            {"label": elm, "value": elm} for elm in x_elm
        ]
        settings["Color by"]["options"] = [
            {"label": elm, "value": elm} for elm in colorby_elm
        ]
        return tuple(
            update_relevant_components(
                id_list=selector_ids,
                update_info=[
                    {
                        "new_value": values.get(prop, no_update),
                        "conditions": {"selector": selector},
                    }
                    for selector, values in settings.items()
                ],
            )
            for prop in ["disable", "value", "options"]
        )

    @app.callback(
        Output(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "undef"},
            "multi",
        ),
        Output(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "undef"},
            "value",
        ),
        Input(get_uuid("page-selected"), "data"),
        Input({"id": get_uuid("selections"), "tab": ALL, "selector": ALL}, "value"),
        State({"id": get_uuid("selections"), "tab": ALL, "selector": ALL}, "id"),
        State(get_uuid("tabs"), "value"),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "undef"},
            "options",
        ),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "undef"},
            "multi",
        ),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "undef"},
            "id",
        ),
    )
    def _update_filter_options(
        _selected_page: str,
        selectors: list,
        selector_ids: list,
        selected_tab: str,
        filter_options: list,
        filter_multi: list,
        filter_ids: list,
    ) -> tuple:

        page_selections = {
            id_value["selector"]: values
            for id_value, values in zip(selector_ids, selectors)
            if id_value["tab"] == selected_tab
        }
        page_filter_settings = {
            id_value["selector"]: {"options": options, "multi": multi}
            for id_value, options, multi in zip(
                filter_ids, filter_options, filter_multi
            )
            if id_value["tab"] == selected_tab
        }

        selected_data = []
        if selected_tab == "voldist":
            selected_data = [
                page_selections[x]
                for x in ["Color by", "Subplots", "X Response", "Y Response"]
            ]
        if selected_tab == "table" and page_selections["Group by"] is not None:
            selected_data = page_selections["Group by"]
        if selected_tab == "tornado":
            selected_data = ["SENSNAME"]

        output = {}
        for selector in ["SOURCE", "ENSEMBLE", "SENSNAME"]:
            if selector not in page_filter_settings:
                continue
            options = [x["value"] for x in page_filter_settings[selector]["options"]]
            multi = selector in selected_data
            selector_is_multi = page_filter_settings[selector]["multi"]
            if not multi and selector_is_multi:
                values = [
                    "rms_seed"
                    if selector == "SENSNAME" and "rms_seed" in options
                    else options[0]
                ]
            elif multi and not selector_is_multi:
                values = options
            else:
                multi = values = no_update
            output[selector] = {"multi": multi, "values": values}

        # filter tornado on correct fluid based on volume response chosen
        output["FLUID_ZONE"] = {}
        if selected_tab == "tornado" and page_selections["mode"] == "locked":
            output["FLUID_ZONE"] = {
                "values": [
                    "oil" if page_selections["Response right"] == "STOIIP" else "gas"
                ]
            }

        return (
            update_relevant_components(
                id_list=filter_ids,
                update_info=[
                    {
                        "new_value": values.get("multi", no_update),
                        "conditions": {"tab": selected_tab, "selector": selector},
                    }
                    for selector, values in output.items()
                ],
            ),
            update_relevant_components(
                id_list=filter_ids,
                update_info=[
                    {
                        "new_value": values.get("values", no_update),
                        "conditions": {"tab": selected_tab, "selector": selector},
                    }
                    for selector, values in output.items()
                ],
            ),
        )

    @app.callback(
        Output(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "REAL"},
            "value",
        ),
        Output(
            {"id": get_uuid("filters"), "tab": ALL, "element": "real_text"}, "children"
        ),
        Input({"id": get_uuid("filters"), "tab": ALL, "component_type": ALL}, "value"),
        State(get_uuid("tabs"), "value"),
        State({"id": get_uuid("filters"), "tab": ALL, "component_type": ALL}, "id"),
        State({"id": get_uuid("filters"), "tab": ALL, "element": "real_text"}, "id"),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "REAL"},
            "id",
        ),
    )
    def _update_realization_filter_and_text(
        reals: list,
        selected_tab: str,
        reals_ids: list,
        real_string_ids: list,
        real_filter_id: list,
    ) -> tuple:
        """Callback that updates the selected relization info and text"""
        if selected_tab == "fipqc":
            raise PreventUpdate

        index = [x["tab"] for x in reals_ids].index(selected_tab)
        real_list = [int(real) for real in reals[index]]

        if reals_ids[index]["component_type"] == "range":
            real_list = list(range(real_list[0], real_list[1] + 1))
            text = f"{real_list[0]}-{real_list[-1]}"
        else:
            text = create_range_string(real_list)

        return (
            update_relevant_components(
                id_list=real_filter_id,
                update_info=[
                    {"new_value": real_list, "conditions": {"tab": selected_tab}}
                ],
            ),
            update_relevant_components(
                id_list=real_string_ids,
                update_info=[{"new_value": text, "conditions": {"tab": selected_tab}}],
            ),
        )

    @app.callback(
        Output(
            {
                "id": get_uuid("filters"),
                "tab": ALL,
                "element": "real-slider-wrapper",
            },
            "children",
        ),
        Input(
            {
                "id": get_uuid("filters"),
                "tab": ALL,
                "element": "real-selector-option",
            },
            "value",
        ),
        State(get_uuid("selections"), "data"),
        State(get_uuid("page-selected"), "data"),
        State(get_uuid("tabs"), "value"),
        State(
            {
                "id": get_uuid("filters"),
                "tab": ALL,
                "element": "real-selector-option",
            },
            "id",
        ),
        State(
            {
                "id": get_uuid("filters"),
                "tab": ALL,
                "element": "real-slider-wrapper",
            },
            "id",
        ),
    )
    def _update_realization_selected_info(
        input_selectors: list,
        selections: dict,
        selected_page: str,
        selected_tab: str,
        input_ids: list,
        wrapper_ids: list,
    ) -> list:
        if selected_tab == "fipqc":
            raise PreventUpdate

        reals = volumemodel.realizations
        prev_selection = (
            selections[selected_page]["filters"].get("REAL", [])
            if selections is not None and selected_page in selections
            else None
        )
        selected_component = [
            value
            for id_value, value in zip(input_ids, input_selectors)
            if id_value["tab"] == selected_tab
        ][0]
        selected_reals = prev_selection if prev_selection is not None else reals

        component = (
            wcc.RangeSlider(
                id={
                    "id": get_uuid("filters"),
                    "tab": selected_tab,
                    "component_type": selected_component,
                },
                value=[min(selected_reals), max(selected_reals)],
                min=min(reals),
                max=max(reals),
                marks={str(i): {"label": str(i)} for i in [min(reals), max(reals)]},
            )
            if selected_component == "range"
            else wcc.SelectWithLabel(
                id={
                    "id": get_uuid("filters"),
                    "tab": selected_tab,
                    "component_type": selected_component,
                },
                options=[{"label": i, "value": i} for i in reals],
                value=selected_reals,
                size=min(20, len(reals)),
            )
        )
        return update_relevant_components(
            id_list=wrapper_ids,
            update_info=[{"new_value": component, "conditions": {"tab": selected_tab}}],
        )

    @app.callback(
        Output(
            {"id": get_uuid("selections"), "selector": ALL, "tab": "tornado"}, "options"
        ),
        Output(
            {"id": get_uuid("selections"), "selector": ALL, "tab": "tornado"}, "value"
        ),
        Output(
            {"id": get_uuid("selections"), "selector": ALL, "tab": "tornado"},
            "disabled",
        ),
        Input(
            {"id": get_uuid("selections"), "selector": "mode", "tab": "tornado"},
            "value",
        ),
        State({"id": get_uuid("selections"), "selector": ALL, "tab": "tornado"}, "id"),
    )
    def _update_tornado_selections_from_mode(mode: str, selector_ids: list) -> tuple:
        settings = {}
        if mode == "custom":
            settings["Response left"] = settings["Response right"] = {
                "options": [{"label": i, "value": i} for i in volumemodel.responses],
                "disabled": False,
            }
        else:
            volume_options = [
                x for x in ["STOIIP", "GIIP"] if x in volumemodel.responses
            ]
            settings["Response left"] = {
                "options": [{"label": "BULK", "value": "BULK"}],
                "value": "BULK",
                "disabled": True,
            }
            settings["Response right"] = {
                "options": [{"label": i, "value": i} for i in volume_options],
                "value": volume_options[0],
                "disabled": len(volume_options) == 1,
            }

        return tuple(
            update_relevant_components(
                id_list=selector_ids,
                update_info=[
                    {
                        "new_value": values.get(prop, no_update),
                        "conditions": {"selector": selector},
                    }
                    for selector, values in settings.items()
                ],
            )
            for prop in ["options", "value", "disabled"]
        )

    @app.callback(
        Output(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "region"},
            "value",
        ),
        Output(
            {"id": get_uuid("filters"), "wrapper": ALL, "tab": ALL, "type": "region"},
            "style",
        ),
        Input(
            {"id": get_uuid("filters"), "tab": ALL, "element": "region-selector"},
            "value",
        ),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "selector": ALL, "type": "region"},
            "id",
        ),
        State(get_uuid("tabs"), "value"),
        State(get_uuid("page-selected"), "data"),
        State(get_uuid("selections"), "data"),
        State(
            {"id": get_uuid("filters"), "wrapper": ALL, "tab": ALL, "type": "region"},
            "id",
        ),
        State(
            {"id": get_uuid("filters"), "tab": ALL, "element": "region-selector"},
            "id",
        ),
        prevent_initial_call=True,
    )
    def update_region_filters(
        selected_reg_filter: list,
        reg_filter_ids: list,
        selected_tab: str,
        selected_page: str,
        selections: dict,
        wrapper_ids: list,
        reg_select_ids: list,
    ) -> tuple:
        """
        Callback to update the visible region filter between FIPNUM or ZONE/REGION.
        When changing, the active selection will be used to set the new selection.
        Note this callback will only be used for cases where each FIPNUM belongs to
        a unique ZONE and REGION.
        """
        selected = [
            value
            for id_value, value in zip(reg_select_ids, selected_reg_filter)
            if id_value["tab"] == selected_tab
        ]

        df = volumemodel.dataframe
        filters = selections[selected_page]["filters"]

        values = {}
        if selected[0] != "fipnum":
            values["FIPNUM"] = df["FIPNUM"].unique()
            for elm in ["REGION", "ZONE"]:
                values[elm] = df.loc[df["FIPNUM"].isin(filters["FIPNUM"])][elm].unique()

        else:
            values["REGION"] = df["REGION"].unique()
            values["ZONE"] = df["ZONE"].unique()
            mask = (df["REGION"].isin(filters["REGION"])) & (
                df["ZONE"].isin(filters["ZONE"])
            )
            values["FIPNUM"] = df.loc[mask]["FIPNUM"].unique()

        styles = {}
        styles["FIPNUM"] = {"display": "none" if selected[0] != "fipnum" else "block"}
        styles["REGION"] = {"display": "none" if selected[0] == "fipnum" else "block"}
        styles["ZONE"] = {"display": "none" if selected[0] == "fipnum" else "block"}

        return (
            update_relevant_components(
                id_list=reg_filter_ids,
                update_info=[
                    {
                        "new_value": value,
                        "conditions": {"selector": selector, "tab": selected_tab},
                    }
                    for selector, value in values.items()
                ],
            ),
            update_relevant_components(
                id_list=wrapper_ids,
                update_info=[
                    {
                        "new_value": style,
                        "conditions": {"wrapper": selector, "tab": selected_tab},
                    }
                    for selector, style in styles.items()
                ],
            ),
        )

    @app.callback(
        Output(
            {"id": get_uuid("selections"), "tab": "src-comp", "selector": "Ignore <"},
            "value",
        ),
        Input(
            {"id": get_uuid("selections"), "tab": "src-comp", "selector": "Response"},
            "value",
        ),
    )
    def _reset_ignore_value_source_comparison(_response_change: str) -> float:
        """reset ignore value when new response is selected"""
        return 0

    @app.callback(
        Output(
            {"id": get_uuid("selections"), "tab": "ens-comp", "selector": "Ignore <"},
            "value",
        ),
        Input(
            {"id": get_uuid("selections"), "tab": "ens-comp", "selector": "Response"},
            "value",
        ),
    )
    def _reset_ignore_value_ens_comparison(_response_change: str) -> float:
        """reset ignore value when new response is selected"""
        return 0
