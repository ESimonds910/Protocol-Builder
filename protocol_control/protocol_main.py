import ipywidgets as ipw
from IPython.display import display
import pandas as pd
import psycopg2 as pg2
import datetime as dt
from config import config
from protocol_control.template_output import TemplateOutput

STYLE = {'description_width': 'initial'}
PROJECT_LIST = ["...", "Akita", "Spaniel", "Dalmatian", "Xolo", "Xochaso"]

PARAMS = config()
CONN = pg2.connect(**PARAMS)


class Protocol:
    """
    This class is to standardize the protocol used for HiPrBind runs, and link run components (e.g. reagents,
    consumables) to inventory database.
    """
    def __init__(self):
        # Postgres query
        self.cur = CONN.cursor()
        # Run tracking info
        self.run_tracking_dict = {}

        # Used for run logs and update queries
        self.all_reagents_df = pd.DataFrame()
        self.all_consumables_df = pd.DataFrame()

        # Set widgets for required inputs
        self.proj_info_head = ipw.HTML('<h5><b>Project Info: </b></h5>')

        # Creates query to grab project names from database for widget dropdown
        proj_name_query = """
            SELECT DISTINCT(project_reagents.proj_id), proj_name FROM project_reagents
            INNER JOIN projects
            ON projects.proj_id = project_reagents.proj_id
        """
        proj_name_data = self.query_call(proj_name_query)
        proj_name_dict = {proj[1]: proj[0] for proj in proj_name_data}
        proj_name_dict['...'] = 0
        self.project_choice = ipw.Dropdown(description="Choose project: ", options=proj_name_dict, value=0, style=STYLE)

        self.run_type = ipw.Dropdown(description="Choose run type: ", options=["SSF", "Fermentation"], style=STYLE)
        self.bind_scheme = ipw.IntText(description="Choose # of bind schemes: ", style=STYLE)
        self.plates_head = ipw.HTML('<h5><b>Plates: </b></h5>')
        self.predilution_plates = ipw.Checkbox(description='Predilution Plates', indent=False, style=STYLE)
        self.source_plates = ipw.IntText(description='Source plates:', indent=False, style=STYLE)
        self.proxiplates = ipw.Dropdown(description='Replicate plates: ', options=['0', 'n + 2', 'n * 2'], style=STYLE)
        self.db_head = ipw.HTML('<h5><b>Source Resuspension / Greiner Dilution Volumes: </b></h5>')
        self.dbi_vol = ipw.IntText(description="DBI uL required / well: ", style=STYLE)
        self.dbii_vol = ipw.IntText(description="DBII uL required / well: ", style=STYLE)
        self.manual_edit_button = ipw.Button(description='Manual Edit', button_style='info')
        self.manual_edit_button.on_click(self.manual_edit)
        self.disabled_buttons = True
        self.input_vol_head = ipw.HTML('<h5><b>Serial Dilutions: </b></h5>')
        self.input_vol_1 = ipw.IntText(description="Volume 1 (uL): ", style=STYLE)
        self.input_vol_2 = ipw.IntText(description="Volume 2 (uL): ", style=STYLE)
        self.input_vol_3 = ipw.IntText(description="Volume 3 (uL): ", style=STYLE)
        self.input_vol_4 = ipw.IntText(description="Volume 4 (uL): ", style=STYLE)
        self.point_dilution = ipw.Dropdown(description="Choose 4 or 8 point dilution: ", options={'4 point': 4, '8 point': 8}, value=4, style=STYLE)
        self.cell_pellet = ipw.IntText(description="Cell pellet size:", value=0, style=STYLE)
        self.input_vol_display = ipw.VBox([
            self.input_vol_head,
            self.point_dilution,
            self.cell_pellet,
            self.input_vol_1,
            self.input_vol_2,
            self.input_vol_3,
            self.input_vol_4
        ])
        self.output_vol_1 = ipw.FloatText(description="Volume 1", style=STYLE)
        self.output_vol_2 = ipw.FloatText(description="Volume 2", style=STYLE)
        self.output_vol_3 = ipw.FloatText(description="Volume 3", style=STYLE)
        self.output_vol_4 = ipw.FloatText(description="Volume 4", style=STYLE)
        self.output_vol_5 = ipw.FloatText(description="Volume 5", style=STYLE)
        self.output_vol_6 = ipw.FloatText(description="Volume 6", style=STYLE)
        self.output_vol_7 = ipw.FloatText(description="Volume 7", style=STYLE)
        self.output_vol_8 = ipw.FloatText(description="Volume 8", style=STYLE)
        self.output_vol_display_1 = ipw.VBox([self.output_vol_1, self.output_vol_2, self.output_vol_3, self.output_vol_4])
        self.output_vol_display_2 = ipw.VBox([self.output_vol_5, self.output_vol_6, self.output_vol_7, self.output_vol_8])
        self.output_vol_display_all = ipw.HBox([self.output_vol_display_1])

        self.pd_vol_head = ipw.HTML('<h5><b>Predilution DBI vol (uL):</b></h5>')
        self.pd_1_vol = ipw.IntText(description='Plate 1: ', style=STYLE)
        self.pd_2_vol = ipw.IntText(description='Plate 2: ', style=STYLE)
        self.pd_3_vol = ipw.IntText(description='Plate 3: ', style=STYLE)
        self.pd_4_vol = ipw.IntText(description='Plate 4: ', style=STYLE)
        self.pd_vol_display = ipw.VBox([
            self.pd_vol_head,
            self.pd_1_vol,
            self.pd_2_vol,
            self.pd_3_vol,
            self.pd_4_vol
        ])
        self.pd_spike_head = ipw.HTML('<h5><b>Predilution Spike vol (uL):</b></h5>')
        self.pd_1_spike = ipw.IntText(description='Spike 1: ', style=STYLE)
        self.pd_2_spike = ipw.IntText(description='Spike 2: ', style=STYLE)
        self.pd_3_spike = ipw.IntText(description='Spike 3: ', style=STYLE)
        self.pd_4_spike = ipw.IntText(description='Spike 4: ', style=STYLE)
        self.pd_spike_display = ipw.VBox([
            self.pd_spike_head,
            self.pd_1_spike,
            self.pd_2_spike,
            self.pd_3_spike,
            self.pd_4_spike
        ])
        self.predilution_options_display = ipw.HBox([])

        # Boxes to display in form
        self.run_type_display = ipw.VBox([self.run_type])
        self.bind_scheme_display = ipw.VBox([self.bind_scheme])
        self.predilution_plates_display = ipw.VBox([self.predilution_plates])
        self.source_plates_display = ipw.VBox([self.source_plates])
        self.proxiplates_display = ipw.VBox([self.proxiplates])

        # Proxiplate output display
        # self.total_proxiplate_label = ipw.Label("Total proxiplates for run:")
        self.total_proxiplate = ipw.IntText(description='Total proxiplates for run: ', value=0, style=STYLE, disabled=True)
        self.total_proxiplate_display = ipw.HBox([self.total_proxiplate])

        # Greiner plate output display
        self.total_greiner = ipw.IntText(description='Total greiner plates for run: ', value=0, style=STYLE, disabled=True)

        # 96w plate output display
        self.pd_plates = ipw.IntText(description='96w Predilution plates neeeded: ', value=0, style=STYLE, disabled=True)
        self.total_pd_plates = ipw.IntText(description='96w Predilution plates needed: ', value=0, style=STYLE, disabled=True)

        self.total_plate_display = ipw.HBox([
            self.total_proxiplate,
            self.total_greiner,
            self.total_pd_plates
        ])
        # Fixed variables
        self.proxi_wells = 384
        self.source_wells = 96
        self.proxi_well_vol = 6
        self.ml_ul_conv = 1000
        self.tempest_comp_one = 6
        self.tempest_comp_two = 8
        self.tempest_comp_three = 3

        # ASI and ASII output display
        self.assay_one_label = ipw.HTML('<h5><b>Total ASI required for run:</b></h5>')
        self.assay_one_rxn = ipw.FloatText(description='ASI for rxn: ', style=STYLE, disabled=True)
        self.assay_one_dead = ipw.FloatText(description='ASI dead vol: ', style=STYLE, disabled=True)
        self.assay_one_req = ipw.FloatText(description='ASI mL needed: ', style=STYLE, disabled=True)
        self.assay_one_display = ipw.VBox([self.assay_one_label,
                                           self.assay_one_rxn,
                                           self.assay_one_dead,
                                           self.assay_one_req])

        self.assay_two_label = ipw.HTML('<h5><b>Total ASII required for run:</b></h5>')
        self.assay_two_rxn = ipw.FloatText(description='ASII for rxn: ', style=STYLE, disabled=True)
        self.assay_two_dead = ipw.FloatText(description='ASII dead vol: ', style=STYLE, disabled=True)
        self.assay_two_req = ipw.FloatText(description='ASII mL needed: ', style=STYLE, disabled=True)
        self.assay_two_display = ipw.VBox([self.assay_two_label,
                                           self.assay_two_rxn,
                                           self.assay_two_dead,
                                           self.assay_two_req])

        self.assay_display = ipw.HBox([self.assay_one_display, self.assay_two_display])

        # Dilution Buffer
        self.dbi_total = ipw.IntText(description="DBI mL needed: ", value=0, style=STYLE, disabled=True)
        self.dbii_total = ipw.IntText(description="DBII mL needed: ", value=0, style=STYLE, disabled=True)

        self.dbi_display = ipw.VBox([self.dbi_total])
        self.dbii_display = ipw.VBox([self.dbii_total])
        self.db_display = ipw.HBox([self.dbi_display, self.dbii_display])

        # Assay dataframe for display
        self.as_df = pd.DataFrame()
        self.as_table_row = ipw.VBox()
        self.as_table_header = ipw.VBox()
        self.as_table_display = ipw.VBox([self.as_table_header, self.as_table_row])

        # Consumables table and display
        self.consumables_dict = {}
        self.consumables_display = ipw.VBox()

        # Capture inputs button
        self.capture_head = ipw.HTML('<h4><b>Log this run into Database</b></h4>')
        self.capture_button = ipw.Button(description="Log Run", button_style='info')
        self.capture_button.on_click(self.capture_inputs)
        self.to_protocol_button = ipw.Button(description='Protocol', button_style='info')
        self.to_protocol_button.on_click(self.protocol_template)
        self.capture_display = ipw.VBox([
            self.capture_head,
            self.capture_button,
            self.to_protocol_button
        ])

        # Standard Section
        self.standard_include = ipw.Checkbox(description="Include Standard Curve", indent=False)
        self.standard_id = None
        # Standard inputs
        self.standard_box_header = ipw.HTML('<h5><b>Standard Concentrations to be used:</b></h5>')
        self.standard_conc_1 = ipw.FloatText(description='#1 nM: ')
        self.standard_conc_2 = ipw.FloatText(description='#2 nM: ')
        self.standard_conc_3 = ipw.FloatText(description='#3 nM: ')
        self.standard_conc_4 = ipw.FloatText(description='#4 nM: ')
        self.standard_conc_5 = ipw.FloatText(description='#5 nM: ')
        self.standard_conc_6 = ipw.FloatText(description='#6 nM: ')

        self.standard_wells = ipw.IntText(description='# of columns/rows for standard: ', value=2, style=STYLE)
        self.standard_plates = ipw.IntText(description='# of source plates with standard: ', style=STYLE)
        self.standard_vol = ipw.IntText(description='Volume uL per well: ', style=STYLE)
        self.standard_display = ipw.VBox()
        self.standard_info = [self.standard_box_header,
                              ipw.HBox([
                                ipw.VBox([
                                    self.standard_conc_1,
                                    self.standard_conc_2,
                                    self.standard_conc_3,
                                    self.standard_conc_4,
                                    self.standard_conc_5,
                                    self.standard_conc_6
                                ]),
                                ipw.VBox([
                                    self.standard_wells,
                                    self.standard_plates,
                                    self.standard_vol
                                ])
                            ])]

        # Fixed buffer volume
        self.standard_buffer_amt = 300

        # Standard outputs
        self.standard_total_vol = ipw.FloatText(description='Total Volume mL needed for Standard: ', style=STYLE)
        self.standard_total_stock = ipw.FloatText(description='Total Volume uL stocked needed: ', style=STYLE)
        self.standard_total_dbi = ipw.FloatText(description='Total Volume uL DBI needed: ', style=STYLE)
        self.standard_scheme_total_dbi = 0

        self.standard_output_info = [ipw.HTML('<h3>Standard Curve Prep</h3>'), ipw.VBox()]
        self.standard_output_display = ipw.VBox()

        # Text box for run notes
        self.run_notes = ipw.Textarea(description='Run notes:', style=STYLE)
        self.run_notes_display = ipw.VBox([
            ipw.HTML('<h5><b>Record Notes</b></h5>'),
            self.run_notes
        ])


        # Input Display Form
        self.form_display = ipw.VBox([
            self.proj_info_head,
            ipw.HBox([
                ipw.VBox([
                    self.project_choice,
                    self.run_type_display,
                    self.bind_scheme_display,
                    self.plates_head
                ]),
                self.standard_include
            ]),
            ipw.HBox([
                self.source_plates_display,
                self.predilution_plates_display,
            ]),
            self.proxiplates_display,
            self.db_head,
            ipw.HBox([
                self.dbi_vol,
                self.dbii_vol
            ]),
            self.input_vol_display,
            self.predilution_options_display,
            self.standard_display,
            self.run_notes_display
        ])

    def show_form_display(self):
        def proxi_display(source, replicates, predilution, pd1, pd2, pd3, pd4, dbi, standard_inc):
            # Show predilution options
            if predilution:
                self.predilution_options_display.children = [self.pd_vol_display, self.pd_spike_display]
            # Determine proxiplates and greiner plates
            self.pd_plates.value = 4 - [pd1, pd2, pd3, pd4].count(0)
            total_num = source * (1 + self.pd_plates.value)
            self.total_greiner.value = total_num
            self.total_pd_plates.value = self.pd_plates.value * source

            if replicates == 'n + 2':
                if total_num == 1:
                    total_num += 1
                else:
                    total_num += 2
            elif replicates == 'n * 2':
                total_num *= 2

            self.total_proxiplate.value = str(total_num)

            # Show standard section
            if standard_inc:
                self.standard_display.children = self.standard_info
                self.standard_plates.value = source
                self.standard_vol.value = dbi
                self.standard_output_display.children = self.standard_output_info

        plate_num = ipw.interactive(proxi_display,
                                    source=self.source_plates,
                                    replicates=self.proxiplates,
                                    predilution=self.predilution_plates,
                                    pd1=self.pd_1_vol,
                                    pd2=self.pd_2_vol,
                                    pd3=self.pd_3_vol,
                                    pd4=self.pd_4_vol,
                                    dbi=self.dbi_vol,
                                    standard_inc=self.standard_include)
        input_header = ipw.HTML("<h3>Create Protocol</h3>")
        display(input_header, self.form_display)
        # display(plate_num)

    def show_outputs(self):
        def calcs(plates, greiner, source, pd1, pd2, pd3, pd4, dbi, dbii, pd_plates, proj_name, standard_inc, standard_plates, standard_wells, standard_vol, conc_1, conc_2, conc_3, conc_4, conc_5, conc_6):
            if standard_inc:
                # # Standard output section
                try:
                    fold_1 = round(conc_1 / conc_2, 0)
                    fold_2 = round(conc_2 / conc_3, 0)
                    fold_3 = round(conc_3 / conc_4, 0)
                    fold_4 = round(conc_4 / conc_5, 0)
                    fold_5 = round(conc_5 / conc_6, 0)
                except ZeroDivisionError:
                    pass
                else:
                    # self.standard_total_vol.value = standard_plates * (standard_wells * 6) * (
                    #             standard_vol + self.standard_buffer_amt) / self.ml_ul_conv
                    standard_base_wvol = standard_plates * standard_wells * (standard_vol + self.standard_buffer_amt)
                    self.standard_total_vol.value = standard_base_wvol * (1 / (fold_1 - 1) + 1)

                    # Add query for standard conc data
                    if proj_name == '...':
                        pass
                    else:
                        # proj_name = proj_name.lower()
                        query = f"""
                            SELECT standard_id, standard_name, stock_conc_nm, on_hand
                            FROM project_standards
                            WHERE proj_id = {proj_name}
                        """
                        # Call query function to retrieve data from database
                        query_data = self.query_call(query)

                        # Extract data from the query
                        standard_stock_conc = float(query_data[0][2])
                        self.standard_id = int(query_data[0][0])
                        # Additional calculations for stock conc needed and DBI needed to prepare solution
                        self.standard_total_stock.value = round((conc_1 * self.standard_total_vol.value) / standard_stock_conc, 2)
                        self.standard_total_dbi.value = round(self.standard_total_vol.value - self.standard_total_stock.value, 2)

                        # Calculating total DBI needed for standard prep; to be added to total DBI needed for run
                        self.standard_scheme_total_dbi = (self.standard_total_dbi.value + standard_base_wvol * 5) / self.ml_ul_conv

                        # Display box for standard prep scheme
                        standard_display_boxwidth = '12%'
                        standard_base_wvol_display = ipw.VBox([
                            ipw.HBox([
                                ipw.VBox([
                                    ipw.HTML(value='<h5><b>Standard Dilution Scheme</b></h5>'),
                                    ipw.HBox([
                                                 ipw.HTML(value="",
                                                          layout=ipw.Layout(width=standard_display_boxwidth)),
                                                 ipw.Label(value='Well 1',
                                                           layout=ipw.Layout(width=standard_display_boxwidth))
                                             ] + [
                                        ipw.Label(
                                            value=f'Well {num}',
                                            layout=ipw.Layout(width=standard_display_boxwidth)
                                        ) for num in range(2, 7)
                                    ]),
                                    ipw.HBox([
                                                 ipw.Label(value='Add DBI:', style=STYLE,
                                                           layout=ipw.Layout(
                                                               width=standard_display_boxwidth,
                                                               display='flex',
                                                               justify_content='flex-end'
                                                           )),
                                                 ipw.Text(value=str(self.standard_total_vol.value),
                                                          layout=ipw.Layout(width=standard_display_boxwidth))
                                             ] + [
                                        ipw.Text(
                                            value=str(standard_base_wvol),
                                            layout=ipw.Layout(width=standard_display_boxwidth)
                                        ) for num in range(2, 7)
                                    ]),
                                    ipw.HBox([
                                                 ipw.Label(value='Transfer:', style=STYLE,
                                                           layout=ipw.Layout(
                                                              width=standard_display_boxwidth,
                                                              display='flex',
                                                              justify_content='flex-end'
                                                          )),
                                                 ipw.Text(value="0", style=STYLE,
                                                          layout=ipw.Layout(width=standard_display_boxwidth))
                                             ] + [
                                        ipw.Text(
                                            value=str(round(standard_base_wvol / (fold - 1), 0)),
                                            layout=ipw.Layout(width=standard_display_boxwidth)
                                        ) for fold in [fold_1, fold_2, fold_3, fold_4, fold_5]
                                    ])
                                ])
                            ])
                        ])

                        self.standard_output_info[1].children = [
                            ipw.HBox([
                                self.standard_total_vol,
                                self.standard_total_stock,
                                self.standard_total_dbi
                            ]),
                            ipw.VBox([
                                standard_base_wvol_display
                            ])
                        ]

            # Reset query dataframe
            self.all_reagents_df = pd.DataFrame()
            # Assay solution calculations
            as_rxn_vol = (self.proxi_well_vol * self.proxi_wells * int(plates)) / self.ml_ul_conv
            self.assay_one_rxn.value = as_rxn_vol
            self.assay_two_rxn.value = as_rxn_vol

            as_dead_vol = (self.proxi_well_vol *
                           int(plates) *
                           self.tempest_comp_one *
                           self.tempest_comp_two) / self.ml_ul_conv + self.tempest_comp_three
            self.assay_one_dead.value = as_dead_vol
            self.assay_two_dead.value = as_dead_vol

            self.assay_one_req.value = -(-((as_rxn_vol + as_dead_vol) // 1))
            self.assay_two_req.value = -(-((as_rxn_vol + as_dead_vol) // 1))

            # Dilution Buffer calculations
            pd_total_vol = -(-((sum([pd1, pd2, pd3, pd4]) * int(source) * self.source_wells) / self.ml_ul_conv) // 1)

            self.dbi_total.value = -(-((int(source) * dbi * self.source_wells) / self.ml_ul_conv) // 1) + pd_total_vol + self.standard_scheme_total_dbi
            self.dbii_total.value = -(-((int(greiner) * dbii * self.proxi_wells) / self.ml_ul_conv) // 1)

            # Assay table calculations
            if proj_name == "...":
                pass
            else:
                # proj_name = proj_name.lower()
                # Used for visual display and manual updates
                all_return_data = None

                # Perhaps change range to include binding scheme?
                for query in range(1, 3):
                    as_query = f"""
                    SELECT reagents.reagent_id, reagent, concentration_ugul, on_hand, project_reagents.desired_conc, 
                    CASE 
                        WHEN reagent ILIKE 'lysozyme%' THEN ROUND(on_hand - {self.assay_one_req.value} * project_reagents.desired_conc / concentration_ugul * 1000, 2)
                        WHEN reagent ILIKE 'picogreen%' THEN ROUND(on_hand - {self.assay_one_req.value} * project_reagents.desired_conc / concentration_ugul * 1000, 2)
                        WHEN project_reagents.assay_id = 2 THEN ROUND(on_hand - (project_reagents.desired_conc  / concentration_ugul) * 1000 * {self.assay_two_req.value}, 2) 
                        WHEN project_reagents.assay_id = 1 THEN ROUND(on_hand - (project_reagents.desired_conc * {self.assay_one_req.value} * 1000) / concentration_nm, 2)
                        END as ul_remaining,
                    CASE 
                        WHEN reagent ILIKE 'lysozyme%' AND ROUND(on_hand - {self.assay_one_req.value} * project_reagents.desired_conc / concentration_ugul * 1000, 2) < 0 THEN 'Not Enough Stock' 
                        WHEN reagent ILIKE 'picogreen%' AND ROUND(on_hand - {self.assay_one_req.value} * project_reagents.desired_conc / concentration_ugul * 1000, 2) < 0 THEN 'Not Enough Stock' 
                        WHEN project_reagents.assay_id = 2 AND ROUND(on_hand - (project_reagents.desired_conc  / concentration_ugul) * 1000 * {self.assay_two_req.value}, 2)  < 0 THEN 'Not Enough Stock' 
                        WHEN project_reagents.assay_id = 1 AND ROUND(on_hand - (project_reagents.desired_conc * {self.assay_one_req.value} * 1000) / concentration_nm, 2) < 0 THEN 'Not Enough Stock' 
                        ELSE 'In Stock'
                        END as status,
                    CASE 
                        WHEN reagent ILIKE 'lysozyme%' THEN ROUND({self.assay_one_req.value} * project_reagents.desired_conc / concentration_ugul * 1000, 2)
                        WHEN reagent ILIKE 'picogreen%' THEN ROUND({self.assay_one_req.value} * project_reagents.desired_conc / concentration_ugul * 1000, 2)
                        WHEN project_reagents.assay_id = 2 THEN ROUND((project_reagents.desired_conc  / concentration_ugul) * 1000 * {self.assay_two_req.value}, 2) 
                        WHEN project_reagents.assay_id = 1 THEN ROUND((project_reagents.desired_conc * {self.assay_one_req.value} * 1000) / concentration_nm, 2)
                        END as ul_needed
                    FROM project_reagents
                    
                    INNER JOIN reagents 
                    ON project_reagents.reagent_id = reagents.reagent_id
                    WHERE project_reagents.assay_id = {query} AND project_reagents.proj_id = {proj_name}
                    """
                    return_data = self.query_call(as_query)
                    return_data.insert(0, ('ID', 'Reagent', 'Conc ug/ul', 'On Hand', 'Desired conc nM', 'Remaining uL', 'Status', 'Needed ul'))
                    return_data_df = pd.DataFrame(return_data)
                    return_data.insert(0, (f'Assay {query}',))
                    if not all_return_data:
                        all_return_data = return_data
                        self.all_reagents_df = pd.concat([self.all_reagents_df, return_data_df])
                    else:
                        self.all_reagents_df = pd.concat([self.all_reagents_df, return_data_df.iloc[1:, :]])
                        for item in return_data:
                            all_return_data.append(item)

                self.as_table_row.children = [
                                 ipw.HBox([
                                     ipw.HTML(value=f'<b>{str(row_item[i])}</b>',
                                              layout=ipw.Layout(
                                                  width='12%',
                                                  border='solid'),
                                              disabled=True) if row_item[i] == 'Assay 1' or row_item[i] == 'Assay 2'
                                                                or row_item[0] == 'ID' else
                                     ipw.Text(value=str(row_item[i]), layout=ipw.Layout(width='12%', border='0.5px solid'), disabled=True)
                                     for i in range(0, len(row_item))
                                 ]) for row_item in all_return_data]

                # Update and show consumables
                consumables_table = [['ID', 'Item', 'On hand', 'Remaining', 'Status']]
                self.consumables_dict = {'384w proxiplates': plates,
                                         '384w dilution plates clear': greiner,
                                         '50mL dark conicals': 2,
                                         '8w trough reservoir': 1,
                                         '300mL reservoirs': 1,
                                         '96w MT plates': pd_plates}
                for key, value in self.consumables_dict.items():
                    query = f"""
                        SELECT consumables.item_id, item, on_hand,
                        CASE
                            WHEN item = '{key}' THEN on_hand - {int(value)}
                        END AS remaining,       
                        CASE
                            WHEN item = '{key}' AND (on_hand - {int(value)}) < 0 THEN 'Not Enough Stock' ELSE 'In Stock'
                        END AS status        
                        FROM consumables
                        INNER JOIN project_consumables
                        ON consumables.item_id = project_consumables.item_id
                        WHERE item = '{key}' AND project_consumables.proj_id = {proj_name}
                        """
                    data = self.query_call(query)
                    consumables_table.append(data[0])
                self.all_consumables_df = pd.DataFrame(consumables_table)
                self.consumables_display.children = [
                             ipw.HBox([
                                 ipw.HTML(value=f'<b>{str(row_item[i])}</b>',
                                          layout=ipw.Layout(
                                              width='100%',
                                              border='solid'),
                                          disabled=True) if row_item[0] == 'ID' else
                                 ipw.Text(value=str(row_item[i]), layout=ipw.Layout(width='100%', border='0.5px solid'), disabled=True)
                                 for i in range(0, len(row_item))
                             ]) for row_item in consumables_table]

        calc_outputs = ipw.interactive(calcs,
                                       plates=self.total_proxiplate,
                                       greiner=self.total_greiner,
                                       source=self.source_plates,
                                       pd1=self.pd_1_vol,
                                       pd2=self.pd_2_vol,
                                       pd3=self.pd_3_vol,
                                       pd4=self.pd_4_vol,
                                       dbi=self.dbi_vol,
                                       dbii=self.dbii_vol,
                                       pd_plates=self.total_pd_plates,
                                       proj_name=self.project_choice,
                                       standard_inc=self.standard_include,
                                       standard_plates=self.standard_plates,
                                       standard_wells=self.standard_wells,
                                       standard_vol=self.standard_vol,
                                       conc_1=self.standard_conc_1,
                                       conc_2=self.standard_conc_2,
                                       conc_3=self.standard_conc_3,
                                       conc_4=self.standard_conc_4,
                                       conc_5=self.standard_conc_5,
                                       conc_6=self.standard_conc_6
                                       )

        pxplate_header = ipw.HTML("<h3>Total Plates Needed</h3>")
        as_header = ipw.HTML("<h3>Assay Solution Needed</h3>")
        db_header = ipw.HTML("<h3>Dilution Buffer Needed</h3>")
        asii_table_header = ipw.HTML("<h3>Assay Solution</h3>")
        consumables_header = ipw.HTML("<h3>Consumables List</h3>")
        display(pxplate_header,
                self.total_plate_display,
                as_header,
                self.assay_display,
                db_header,
                self.db_display,
                self.standard_output_display,
                asii_table_header,
                self.as_table_row,
                consumables_header,
                self.consumables_display,
                self.manual_edit_button,
                self.capture_display,
                )

    def manual_edit(self, event):
        if self.disabled_buttons:
            self.total_proxiplate.disabled = False
            self.total_greiner.disabled = False
            self.total_pd_plates.disabled = False
            self.assay_one_rxn.disabled = False
            self.assay_one_dead.disabled = False
            self.assay_one_req.disabled = False
            self.assay_two_rxn.disabled = False
            self.assay_two_dead.disabled = False
            self.assay_two_req.disabled = False
            self.dbi_total.disabled = False
            self.dbii_total.disabled = False

            for row in self.as_table_row.children:
                for cell in row.children:
                    cell.disabled = False
            self.manual_edit_button.description = 'Lock'
            self.disabled_buttons = False
            return self.disabled_buttons
        else:
            self.total_proxiplate.disabled = True
            self.total_greiner.disabled = True
            self.total_pd_plates.disabled = True
            self.assay_one_rxn.disabled = True
            self.assay_one_dead.disabled = True
            self.assay_one_req.disabled = True
            self.assay_two_rxn.disabled = True
            self.assay_two_dead.disabled = True
            self.assay_two_req.disabled = True
            self.dbi_total.disabled = True
            self.dbii_total.disabled = True
            self.disabled_buttons = True
            for row in self.as_table_row.children:
                for cell in row.children:
                    cell.disabled = True
            self.manual_edit_button.description = 'Manual Edit'

    # def define_volumes(self):
    #     def calc_vols(dilutions):
    #         # tab_contents = [str(i) for i in range(1, int(dilutions) + 1)]
    #         # vols = [ipw.Label(description=name, style=STYLE) for name in tab_contents]
    #         # self.volumes_display.children = vols
    #         # children = [ipw.Text(description=name, style=STYLE) for name in tab_contents]
    #         # self.tab.children = children
    #         if dilutions == 4:
    #             self.output_vol_1.value = dilutions
    #             self.output_vol_display_all.children = [self.output_vol_display_1]
    #         if dilutions == 8:
    #             self.output_vol_4.value = dilutions
    #             self.output_vol_display_all.children = [self.output_vol_display_1, self.output_vol_display_2]
    #
    #     show_tab = ipw.interactive(calc_vols, dilutions=self.point_dilution)
    #     display(self.output_vol_display_all)

    def capture_inputs(self, event):
        # Capture date of run
        this_date = dt.date.today()
        this_date = this_date.strftime("%Y-%m-%d")

        # Stock Check
        if 'Not Enough Stock' in self.all_reagents_df[[6]].squeeze().tolist() or 'Not Enough Stock' in self.all_consumables_df[[4]].squeeze().tolist():
            display(ipw.HTML('Not Enough Stock'))
            pass
        else:
            with CONN:
                # Update inventory tables
                # Create list of reagents to update
                update_reagents_tuple = self.all_reagents_df[[1, 5]].apply(tuple, axis=1).squeeze().tolist()
                for item in update_reagents_tuple[1:]:
                    update_item = item[0]
                    update_val = item[1]
                    update_query = f"""
                        UPDATE reagents
                        SET on_hand = {update_val}
                        WHERE reagent = '{update_item}'
                    """
                    self.query_call(update_query)

                # Update project_use_reagents table in inventory tracker
                update_reagent_use_tuple = self.all_reagents_df[[0, 7]].apply(tuple, axis=1).squeeze().tolist()
                for item in update_reagent_use_tuple[1:]:
                    insert_reagent = item[0]
                    insert_val = item[1]
                    insert_query = f"""
                        INSERT INTO project_use_reagents (reagent_id, proj_id, amt_used, date_used)
                        VALUES ({insert_reagent}, {self.project_choice.value}, {insert_val}, '{this_date}')
                    """
                    self.query_call(insert_query)

                # Create list of consumables to update
                update_consumables_table = self.all_consumables_df[[1, 3]].apply(tuple, axis=1).squeeze().tolist()
                for item in update_consumables_table[1:]:
                    update_item = item[0]
                    update_val = item[1]
                    update_query = f"""
                        UPDATE consumables
                        SET on_hand = {update_val}
                        WHERE item = '{update_item}'
                    """
                    self.query_call(update_query)

                # Update project_use_consumables table in inventory tracker
                self.all_consumables_df[5] = self.all_consumables_df[2].apply(lambda x: x if isinstance(x, int) else 0) - \
                                                 self.all_consumables_df[3].apply(lambda x: x if isinstance(x, int) else 0)
                update_consumables_use_tuple = self.all_consumables_df[[0, 5]].apply(tuple, axis=1).squeeze().tolist()
                for item in update_consumables_use_tuple[1:]:
                    insert_item = item[0]
                    insert_val = item[1]
                    insert_query = f"""
                        INSERT INTO project_use_consumables (item_id, proj_id, amt_used, date_used)
                        VALUES ({insert_item}, {self.project_choice.value}, {insert_val}, '{this_date}')
                    """
                    self.query_call(insert_query)

                # Update project_use_standards table in inventory tracking db
                if self.standard_include.value:
                    insert_query = f"""
                        INSERT INTO project_use_standards (standard_id, proj_id, amt_used, date_used)
                        VALUES ({self.standard_id}, {self.project_choice.value}, {self.standard_total_stock.value}, '{this_date}')
                    """
                    self.query_call(insert_query)

                # Update to project_runs table in inventory tracking db
                self.run_tracking_dict = dict(
                    # Inputs
                    proj_id=self.project_choice.value,
                    run_type=self.run_type.value,
                    bind_scheme=self.bind_scheme.value,
                    source_plates=self.source_plates.value,
                    predilution=self.predilution_plates.value,
                    replicates=self.proxiplates.value,
                    dbi_in=self.dbi_vol.value,
                    dbii_in=self.dbii_vol.value,
                    point_dilution=self.point_dilution.value,
                    in_vols=dict(
                        vol_1_in=self.input_vol_1.value,
                        vol_2_in=self.input_vol_2.value,
                        vol_3_in=self.input_vol_3.value,
                        vol_4_in=self.input_vol_4.value
                    ),
                    in_pd_vols=dict(
                        pd_1_vol=self.pd_1_vol.value,
                        pd_2_vol=self.pd_2_vol.value,
                        pd_3_vol=self.pd_3_vol.value,
                        pd_4_vol=self.pd_4_vol.value
                    ),
                    in_pd_spike=dict(
                        spike_1=self.pd_1_spike.value,
                        spike_2=self.pd_2_spike.value,
                        spike_3=self.pd_3_spike.value,
                        spike_4=self.pd_4_spike.value
                    ),
                    standard=self.standard_include.value,
                    standard_concs=dict(
                        standard_conc_1=self.standard_conc_1.value,
                        standard_conc_2=self.standard_conc_2.value,
                        standard_conc_3=self.standard_conc_3.value,
                        standard_conc_4=self.standard_conc_4.value,
                        standard_conc_5=self.standard_conc_5.value,
                        standard_conc_6=self.standard_conc_6.value
                    ),
                    run_notes=self.run_notes.value,
                )
                # Output volume calculations
                # TODO Need to incorporate 8 pt calculations

                    # Outputs
                        # total_pplates=self.total_proxiplate.value,
                        # total_greiner=self.total_greiner.value,
                        # total_pdplates=self.total_pd_plates.value,
                        # total_asi=self.assay_one_req.value,
                        # total_asii=self.assay_two_req.value,
                        # total_dbi=self.dbi_total.value,
                        # total_dbii=self.dbii_total.value,
                        # standard_stock=self.standard_total_stock.value
                    # as_comps_vol=[
                    #     (child.children[0].value, child.children[-1].value) for child in self.as_table_row.children
                    #     if len(child.children) > 1 and 'Reagent' not in child.children[0].value
                    # ]


                # Setup data for INSERT queries into db
                query_cols = ['run_date']
                query_data = [this_date]

                for key, value in self.run_tracking_dict.items():
                    if not isinstance(self.run_tracking_dict[key], dict):
                        query_cols.append(key)
                        query_data.append(value)
                    elif isinstance(self.run_tracking_dict[key], dict):
                        for inner_key, inner_value in self.run_tracking_dict[key].items():
                            query_cols.append(inner_key)
                            query_data.append(inner_value)
                query_cols = tuple(query_cols)
                query_data = tuple(query_data)
                # Query to log run information for future reference
                query = f"""
                    INSERT INTO project_runs ({', '.join(query_cols)})
                    VALUES {query_data}
                """
                self.query_call(query)
                # display(query_cols, query_data, this_date)

    def protocol_template(self, event):
        vol_list = []
        in_vols = [self.input_vol_1.value, self.input_vol_2.value, self.input_vol_3.value, self.input_vol_4.value]
        pellet_conc = (self.dbi_vol.value / self.cell_pellet.value)

        for vol in in_vols:
            dil_factor = ((vol + self.dbii_vol.value) / vol)
            fold_factor = (pellet_conc * dil_factor)
            value = 6 / fold_factor
            vol_list.append(value)
            pellet_conc = fold_factor

        parser_dict = dict(
            Project_Name=self.project_choice.label,
            Volumes=in_vols,
            points=self.point_dilution.value,
            SourcePlates=self.source_plates.value,
            GreinerPlates=self.total_greiner.value,
            ProxiPlates=self.total_proxiplate.value,
            Standard_conc=[
                self.standard_conc_1.value,
                self.standard_conc_2.value,
                self.standard_conc_3.value,
                self.standard_conc_4.value,
                self.standard_conc_5.value,
                self.standard_conc_6.value
            ],
            data=self.all_reagents_df
        )
        TemplateOutput(parser_dict)

    def query_call(self, query):
        self.cur.execute(query)
        if "SELECT" in query:
            data = self.cur.fetchall()
            return data
        elif "INSERT" in query or "UPDATE" in query:
            CONN.commit()

    def show_df(self):
        if not self.all_reagents_df.empty:
            reagents = self.all_reagents_df.iloc[1:, :1].squeeze().tolist()
            data_out = self.all_reagents_df.iloc[:, 1:]
            update_vols = self.all_reagents_df.iloc[:, 4].squeeze().tolist()[1:]
            update_tuple = self.all_reagents_df[[0, 4]].apply(tuple, axis=1).squeeze().tolist()
        else:
            reagents = 'empty df'
            data_out = 'empty df'
            update_vols = 'empty df'
            update_tuple = 'empty df'

        display(self.all_reagents_df, reagents, data_out, update_vols, update_tuple)







