import { Injectable } from '@angular/core';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { DataService } from '../../core/services/data.service';
import { GlobalConstants } from '../../meeting-manager/lib/global-constants';

@Injectable({
  providedIn: 'root',
})
export class PublicFeatureFlagService {
  private readonly featureFlagsUrl = 'v1/harness/feature-flags';

  constructor(
    private dataService: DataService,
    private globalConstants: GlobalConstants,
  ) {}

  isAgendaItemOutcomeEnabled(): Observable<boolean> {
    return this.dataService.get(this.globalConstants.baseUrl + this.featureFlagsUrl).pipe(
      map((response: any) => response?.['agenda-item-outcome'] === true),
      catchError(() => of(false)),
    );
  }
}
