  getAgendaItemSearchResults(updateDisplayedResults = true): void {
    if (!this.agendaItemOutcomeEnabled) {
      this.agendaItemResults = [];
      this.agendaItemTotalResults = 0;
      return;
    }
    this.searchDataSource.searchKeyword = (this.searchDataSource.searchKeyword || '').trim();
    if (!this.hasSearchKeyword) {
      this.resetSearchState();
      return;
    }
    const requestedPageNo = updateDisplayedResults ? this.pageNo || 1 : 1;
    const url = this.globalConstants.baseUrl + this.constants.serviceUrl.searchResult.agendaItemSearch;
    const request: PublicAgendaItemSearchRequest = {
      pageNo: requestedPageNo,
      pageSize: this.pageSize,
      searchKeyword: this.searchDataSource.searchKeyword.trim(),
      startDate: this.searchDataSource.filters.startDate,
      endDate: this.searchDataSource.filters.endDate,
      meetingTypeIds: this.getApiMeetingTypeSelection(),
      votingOutcomes: this.selectedVotingOutcomes,
    };
    this.subscriptions.add(
      this.dataService.post(url, request).subscribe(
        (response: PublicAgendaItemSearchResponse) => {
          this.agendaItemResults = response?.searchResults || [];
          this.agendaItemTotalResults = response?.totalElements || 0;
          if (updateDisplayedResults) {
            this.searchDataSource.totalResults = this.agendaItemTotalResults;
            this.appliedKeyword = request.searchKeyword;
            const paginator: IPaginatorComponent | null = document.querySelector(`[id^=agenda-item-search-page-paginator]`);
            if (paginator) {
              paginator.pageIndex = requestedPageNo - 1;
            }
          }
        },
        (errorObj) => {
          this.snackbarService.showMessage(errorObj.error ? errorObj.error : this.constants.messages.error.internalServerError);
        },
      ),
    );
  }


  private getApiMeetingTypeSelection(): number[] {
    const allMeetingTypesSelected =
      this.selectedMeetingTypes.length === 0 ||
      (this.allMeetingTypes.length > 0 &&
        this.selectedMeetingTypes.length === this.allMeetingTypes.length &&
        this.allMeetingTypes.every((meetingType) => this.selectedMeetingTypes.includes(meetingType.id)));

    return allMeetingTypesSelected ? [-1] : this.selectedMeetingTypes;
  }
