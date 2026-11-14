export interface PublicAgendaItemSearchResult {
  agendaItemId: number;
  itemTitle: string;
  description: string;
  outcomeDescription: string;
  meetingName: string;
  meetingDate: string;
  meetingType: string;
  votingOutcome: string | null;
}

export interface PublicAgendaItemSearchRequest {
  pageNo: number;
  pageSize: number;
  searchKeyword: string;
  startDate: string | null;
  endDate: string | null;
  meetingTypeIds: number[];
  votingOutcomes: string[];
}

export interface PublicAgendaItemSearchResponse {
  searchResults: PublicAgendaItemSearchResult[];
  totalElements: number;
}
