export interface KentRemedyAbbreviationRecord {
  id: string;
  abbreviation_as_printed: string;
  full_name_as_printed: string;
  source_pdf_page: number;
  source_pdf_pages: number[];
  source_column: "left" | "right";
  source_position: { top: number; left: number };
  source_line_as_printed: string;
  continuation_lines: Array<{
    pdf_page: number;
    text_as_printed: string;
    top: number;
    left: number;
    join_rule: string;
  }>;
  verification_status: "transcribed_not_manually_proofread" | "verified" | "needs_review";
}

export interface KentRemedyAbbreviationDataset {
  dataset_id: "kent-pdf-remedy-abbreviation-index";
  source_file_sha256?: string;
  source_record_count?: number;
  proofreading?: {
    status: "partial" | "complete";
    source_record_count: number;
    verified_record_count: number;
    uncertain_record_count: number;
    rejected_record_count: number;
    pending_record_count: number;
    external_data_used: false;
  };
  source: {
    title_heading: string;
    pdf_page_start: number;
    pdf_page_end: number;
  };
  scope: string;
  parsing: {
    method: string;
    continuation_lines_joined_from_layout: Array<{
      abbreviation: string;
      pdf_page: number;
      text_as_printed: string;
    }>;
    unclassified_text_lines: Array<{
      pdf_page: number;
      top: number;
      left: number;
      text: string;
    }>;
    normalization_applied: false;
    canonical_aliases_added: 0;
    external_data_used: false;
  };
  record_count: number;
  duplicate_abbreviation_count: number;
  records: KentRemedyAbbreviationRecord[];
}
