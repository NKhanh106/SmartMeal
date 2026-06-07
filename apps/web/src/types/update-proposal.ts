export interface UpdateField {
  label: string;
  value: unknown;
  unit: string | null;
  display: string;
}

export interface UpdateProposal {
  proposal_id: string;
  target: string;
  fields: UpdateField[];
  summary: string;
  detail: string;
  confidence: number;
  raw_data: Record<string, unknown>;
  source_message: string;
  session_id: string;
}

export interface ProposalConfirmResult {
  success: boolean;
  message: string;
  target: string;
  records_created: number;
  records_updated: number;
}
