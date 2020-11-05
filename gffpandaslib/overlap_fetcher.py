import logging as lg
from itertools import product

import pandas as pd

from gffpandaslib.exporter import Exporter
from gffpandaslib.gff3 import GFF3


class OverlapFetcher:

    def __init__(self, input_obj_a, input_obj_b, set_b_prefix, output_file=None) -> None:
        if isinstance(input_obj_a, GFF3):
            self.input_gff_a = input_obj_a
        else:
            self.input_gff_a = GFF3(input_obj_a, load_metadata=False)
        if isinstance(input_obj_b, GFF3):
            self.input_gff_b = input_obj_b
        else:
            self.input_gff_b = GFF3(input_obj_b, load_metadata=False)
        self.set_b_prefix = set_b_prefix
        self.output_file = output_file

    def fetch_overlaps(self, allow_different_strands=False):
        lg.info(" Fetching overlaps")
        self.input_gff_a.df = self.input_gff_a.df.apply(func=lambda row: self._gen_interval(row), axis=1)
        self.input_gff_b.df = self.input_gff_b.df.apply(func=lambda row: self._gen_interval(row), axis=1)
        if allow_different_strands:
            combinations = product(self.input_gff_a.seq_ids)
        else:
            combinations = product(self.input_gff_a.seq_ids, ["+", "-"])
        for comb in combinations:
            if allow_different_strands:
                gff_a_df = self.input_gff_a.df[(self.input_gff_a.df["seq_id"] == comb[0])]
                gff_b_df = self.input_gff_b.df[(self.input_gff_b.df["seq_id"] == comb[0])]
            else:
                gff_a_df = self.input_gff_a.df[(self.input_gff_a.df["seq_id"] == comb[0]) &
                                               (self.input_gff_a.df["strand"] == comb[1])]
                gff_b_df = self.input_gff_b.df[(self.input_gff_b.df["seq_id"] == comb[0]) &
                                               (self.input_gff_b.df["strand"] == comb[1])]
            for a_indx in gff_a_df.index:
                counter = 0
                for b_indx in gff_b_df.index:
                    if gff_a_df.at[a_indx, "interval"].overlaps(gff_b_df.at[b_indx, "interval"]):
                        counter += 1
                        row = gff_b_df.loc[b_indx].copy()
                        b_attr = self.parse_attributes(row['attributes'])
                        if 'name' in b_attr.keys():
                            overlap_name = b_attr["name"]
                        elif 'label' in b_attr.keys():
                            overlap_name = b_attr["label"]
                        elif 'title' in b_attr.keys():
                            overlap_name = b_attr["title"]
                        elif 'id' in b_attr.keys():
                            overlap_name = b_attr["id"]
                        else:
                            overlap_name = row.at['attributes'].replace(";", "-")
                        if counter > 1:
                            count_prefix = f"_{counter}"
                        else:
                            count_prefix = ""
                        overlap_size = len(set(list(range(gff_b_df.at[b_indx, 'start'],
                                                          gff_b_df.at[b_indx, 'end'] + 1, 1))).intersection(
                            set(list(range(gff_a_df.at[a_indx, 'start'],
                                           gff_a_df.at[a_indx, 'end'] + 1, 1)))))
                        self.input_gff_a.df.at[a_indx, "attributes"] += \
                            f";{self.set_b_prefix}_overlap_start{count_prefix}={gff_b_df.at[b_indx, 'start']}" \
                            f";{self.set_b_prefix}_overlap_end{count_prefix}={gff_b_df.at[b_indx, 'end']}" \
                            f";{self.set_b_prefix}_overlap_size{count_prefix}={overlap_size}nt" \
                            f";{self.set_b_prefix}_comment{count_prefix}={overlap_name}"
                        if allow_different_strands:
                            if gff_a_df.at[a_indx, 'strand'] == gff_b_df.at[b_indx, 'strand']:
                                overlap_strand = "sense"
                            else:
                                overlap_strand = "antisense"
                            f";{self.set_b_prefix}_overlap_strand{count_prefix}={overlap_strand}"
        self.input_gff_a.df.drop("interval", inplace=True, axis=1)
        if self.output_file is not None:
            self._export()

    def _export(self):
        Exporter(self.input_gff_a).export_to_gff(self.output_file)

    @staticmethod
    def _gen_interval(row):
        row["interval"] = pd.Interval(left=row["start"], right=row["end"])
        return row

    @staticmethod
    def parse_attributes(attr_str):
        return {k.lower(): v for k, v in dict(item.split("=") for item in attr_str.split(";")).items()}