export interface VerifiedKentGradePair {
  remedy_id: string;
  grade: 1 | 2 | 3;
  source_pdf_pages: number[];
  source_candidate_ids: string[];
  reviewed_at: string[];
  verification_status: "user_verified_source_checked";
}

export interface VerifiedKentRubric {
  id: string;
  text_as_entered_from_pdf: string;
  source_id: "kent-uploaded-pdf";
  grades: VerifiedKentGradePair[];
  verification_status: "user_verified_source_checked";
}

export interface VerifiedKentRemedy {
  id: string;
  abbreviation_as_printed: string;
  full_name_as_printed_in_pdf_index: string;
  source_id: "kent-uploaded-pdf";
}

export interface VerifiedKentDatabase {
  dataset_id: "curiva-kent-verified-rubric-remedy-grades";
  source: {
    source_id: "kent-uploaded-pdf";
    source_file_sha256: string;
    source_file_name: string;
    grade_key_pdf_page: number;
    grade_key: { ordinary: 1; italics: 2; capitals: 3 };
  };
  data_policy: {
    external_data_used: false;
    generated_rubrics: 0;
    generated_remedies: 0;
    automatic_grade_verification: false;
    note: string;
  };
  rubric_count: number;
  remedy_count: number;
  verified_grade_pair_count: number;
  rubrics: VerifiedKentRubric[];
  remedies: VerifiedKentRemedy[];
}
