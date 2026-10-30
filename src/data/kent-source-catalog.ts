/**
 * Chapter directory transcribed from the uploaded PDF's Contents page (PDF page 62).
 * Internal book page numbers are preserved as printed; they are not PDF page numbers.
 * The page-7 chapter summary differs for Urine (681–692 vs 680–692 on page 62);
 * both source statements are recorded rather than silently reconciled.
 */
export interface KentChapterEntry {
  id: string;
  title: string;
  bookPageStart: number;
  bookPageEnd: number;
  subchapters?: Array<{ id: string; title: string; bookPageStart: number; bookPageEnd: number }>;
  pageSummaryDiscrepancy?: { summaryPdfPage: number; summaryBookPageStart: number; summaryBookPageEnd: number };
}

export const kentSourceCatalog = {
  titleAsPresentedInContents: "KENT'S REPERTORY",
  coverTitleAsPrinted: "KENT’S REPERTOTY",
  contentsPdfPage: 62,
  headingSummaryPdfPage: 7,
  repertoryPdfPageCount: 2834,
  gradeKey: {
    pdfPage: 36,
    capitals: 3,
    italics: 2,
    ordinary: 1,
    sourceWording: "Capitals = 3; Italics = 2; Ordinary = 1",
  },
  chapters: [
    { id: "mind", title: "Mind", bookPageStart: 1, bookPageEnd: 95 },
    { id: "vertigo", title: "Vertigo", bookPageStart: 96, bookPageEnd: 106 },
    { id: "head", title: "Head", bookPageStart: 107, bookPageEnd: 234 },
    { id: "eye", title: "Eye", bookPageStart: 235, bookPageEnd: 270 },
    { id: "vision", title: "Vision", bookPageStart: 271, bookPageEnd: 285 },
    { id: "ear", title: "Ear", bookPageStart: 285, bookPageEnd: 320 },
    { id: "hearing", title: "Hearing", bookPageStart: 321, bookPageEnd: 323 },
    { id: "nose", title: "Nose", bookPageStart: 324, bookPageEnd: 354 },
    { id: "face", title: "Face", bookPageStart: 355, bookPageEnd: 396 },
    { id: "mouth", title: "Mouth", bookPageStart: 397, bookPageEnd: 430 },
    { id: "teeth", title: "Teeth", bookPageStart: 430, bookPageEnd: 447 },
    { id: "throat", title: "Throat", bookPageStart: 448, bookPageEnd: 470 },
    { id: "external-throat", title: "External throat", bookPageStart: 471, bookPageEnd: 475 },
    { id: "stomach", title: "Stomach", bookPageStart: 476, bookPageEnd: 540 },
    { id: "abdomen", title: "Abdomen", bookPageStart: 541, bookPageEnd: 605 },
    { id: "rectum", title: "Rectum", bookPageStart: 606, bookPageEnd: 635 },
    { id: "stool", title: "Stool", bookPageStart: 635, bookPageEnd: 644 },
    {
      id: "urinary-organs", title: "Urinary organs", bookPageStart: 645, bookPageEnd: 680,
      subchapters: [
        { id: "bladder", title: "Bladder", bookPageStart: 645, bookPageEnd: 662 },
        { id: "kidneys", title: "Kidneys", bookPageStart: 662, bookPageEnd: 667 },
        { id: "prostate-gland", title: "Prostate gland", bookPageStart: 667, bookPageEnd: 668 },
        { id: "urethra", title: "Urethra", bookPageStart: 669, bookPageEnd: 680 },
      ],
    },
    {
      id: "urine", title: "Urine", bookPageStart: 680, bookPageEnd: 692,
      pageSummaryDiscrepancy: { summaryPdfPage: 7, summaryBookPageStart: 681, summaryBookPageEnd: 692 },
    },
    { id: "genitalia-male", title: "Genitalia male", bookPageStart: 693, bookPageEnd: 714 },
    { id: "genitalia-female", title: "Genitalia female", bookPageStart: 714, bookPageEnd: 745 },
    { id: "larynx-trachea", title: "Larynx and trachea", bookPageStart: 746, bookPageEnd: 762 },
    { id: "respiration", title: "Respiration", bookPageStart: 762, bookPageEnd: 777 },
    { id: "cough", title: "Cough", bookPageStart: 778, bookPageEnd: 811 },
    { id: "expectoration", title: "Expectoration", bookPageStart: 812, bookPageEnd: 821 },
    { id: "chest", title: "Chest", bookPageStart: 822, bookPageEnd: 883 },
    { id: "back", title: "Back", bookPageStart: 884, bookPageEnd: 951 },
    { id: "extremities", title: "Extremities", bookPageStart: 952, bookPageEnd: 1233 },
    { id: "sleep", title: "Sleep", bookPageStart: 1234, bookPageEnd: 1258 },
    { id: "chill", title: "Chill", bookPageStart: 1259, bookPageEnd: 1277 },
    { id: "fever", title: "Fever", bookPageStart: 1278, bookPageEnd: 1292 },
    { id: "perspiration", title: "Perspiration", bookPageStart: 1293, bookPageEnd: 1302 },
    { id: "skin", title: "Skin", bookPageStart: 1303, bookPageEnd: 1340 },
    { id: "generalities", title: "Generalities", bookPageStart: 1341, bookPageEnd: 1423 },
  ] satisfies KentChapterEntry[],
  sourceDataStatus: "chapter-catalog-only",
} as const;
