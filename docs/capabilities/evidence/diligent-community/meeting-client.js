/* Minification failed. Returning unminified contents.
(3254,46-47): run-time error JS1195: Expected expression: .
(3254,59-60): run-time error JS1003: Expected ':': )
(3255,6-7): run-time error JS1009: Expected '}': s
(3255,6-7): run-time error JS1006: Expected ')': s
(3258,5-7): run-time error JS1009: Expected '}': if
(3258,5-7): run-time error JS1006: Expected ')': if
(3269,66-67): run-time error JS1195: Expected expression: .
(3269,79-80): run-time error JS1003: Expected ':': )
(3270,8-9): run-time error JS1009: Expected '}': s
(3270,8-9): run-time error JS1006: Expected ')': s
(3272,6-7): run-time error JS1006: Expected ')': }
(3271,8): run-time error JS1004: Expected ';'
(3272,7-8): run-time error JS1195: Expected expression: )
(3297,65-66): run-time error JS1195: Expected expression: .
(3297,78-79): run-time error JS1003: Expected ':': )
(3298,9-10): run-time error JS1009: Expected '}': s
(3298,9-10): run-time error JS1006: Expected ')': s
(3302,6-10): run-time error JS1006: Expected ')': else
(3301,7): run-time error JS1004: Expected ';'
(3303,66-67): run-time error JS1195: Expected expression: .
(3303,79-80): run-time error JS1003: Expected ':': )
(3304,8-9): run-time error JS1009: Expected '}': s
(3304,8-9): run-time error JS1006: Expected ')': s
(3307,6): run-time error JS1004: Expected ';'
(3307,6-7): run-time error JS1195: Expected expression: )
(3310,65-66): run-time error JS1195: Expected expression: .
(3310,78-79): run-time error JS1003: Expected ':': )
(3311,7-8): run-time error JS1009: Expected '}': s
(3311,7-8): run-time error JS1006: Expected ')': s
(3315,5-6): run-time error JS1002: Syntax error: }
(3334,4-5): run-time error JS1002: Syntax error: }
(3334,5-6): run-time error JS1195: Expected expression: ,
(3335,20-21): run-time error JS1010: Expected identifier: (
(3338,3-4): run-time error JS1002: Syntax error: }
(3338,4-5): run-time error JS1195: Expected expression: )
(3339,2-3): run-time error JS1002: Syntax error: }
(3797,1-2): run-time error JS1002: Syntax error: }
 */
// Declare namespaces
var Portal = Portal || {};
Portal.MeetingInformationEvents = Portal.MeetingInformationEvents || {};

Portal.MeetingInformation = function (args) {
	//Properties
	var agendaSplitScreenButtonClientId = 'agenda-splitscreen-button';
	var agendaShowMapButtonClientId = 'agenda-show-map-button';
	var agendaHideMapButtonClientId = 'agenda-hide-map-button';
	var documentCoverPdfClientId = 'document-cover-pdf';
	var documentAgendaItemClientId = 'AgendaItem';
	var videoButtonClientId = 'VideoButton';
	var requestToSpeakClientId = 'request-to-speak';

	var meetingTitleClientId = args.meetingTitleId;

	var editButtonClientId = args.editButtonClientId;
	var nextButtonClientId = args.nextButtonId;
	var prevButtonClientId = args.prevButtonId;
	var agendaDocumentClientId = args.agendaDocumentButtonId;
	var videoButtonIdClientId = args.videoButtonId;
	var minutesDocumentClientId = args.minutesDocumentButtonId;
	var documentPrintVersionClientId = args.documentPrintVersionLinkId;
	var trackerWindowClientId = args.trackerWindowClientId;
	var editExternalLinksClientId = args.editExternalLinksClientId;
	var uploadMinutesClientId = args.uploadMinutesClientId;
	var meetingInformationClientId = 'meeting-information';
	var membersListClientId = 'MembersList';

	var meetingDocumentLoadingClientId = 'meeting-document-loading';
	var meetingDocumentClientId = args.meetingDocumentClientId;
	var meetingDocumentUnpublishedClientId = 'meeting-document-unpublished';
	var contentOnly = args.contentOnly;
	var viewMinutes = args.viewMinutes;
	var purchasedVideo = args.purchasedVideo;
	var hasPortalUpdate = args.hasPortalUpdate;

	var map = null;
	var markers = [];
	var defaultLatitude = args.defaultLatitude;
	var defaultLongitude = args.defaultLongitude;
	var defaultZoom = args.defaultZoom;
	var enableSplitScreen = args.enableSplitScreen;

	var boardApplicationTrackers = args.boardApplicationTrackers;

	var meetingId;
	var selectedAgenda;
	var selectedMinutes;
	var splitscreenLinkDocumentId = 0;
	var currentMeetingData;

	var meetingOutputType = {
		Agenda: args.meetingOutputTypes.agenda,
		Minutes: args.meetingOutputTypes.minutes
	};

	var locationItems = [];

	var packageDocumentType = {
		PublishedAgendaOpenPdf: args.packageDocumentTypes.publishedAgendaOpenPdf,
		PublishedAgendaClosedPdf: args.packageDocumentTypes.publishedAgendaClosedPdf,
		PublishedMinutesOpenPdf: args.packageDocumentTypes.publishedMinutesOpenPdf,
		PublishedMinutesClosedPdf: args.packageDocumentTypes.publishedMinutesClosedPdf,

		PublishedAgendaOpenHtml: args.packageDocumentTypes.publishedAgendaOpenHtml,
		PublishedAgendaOpenHtmlSplitScreen: args.packageDocumentTypes.publishedAgendaOpenHtmlSplitScreen,
		PublishedAgendaClosedHtml: args.packageDocumentTypes.publishedAgendaClosedHtml,
		PublishedAgendaClosedHtmlSplitScreen: args.packageDocumentTypes.publishedAgendaClosedHtmlSplitScreen,
		PublishedMinutesOpenHtml: args.packageDocumentTypes.publishedMinutesOpenHtml,
		PublishedMinutesOpenHtmlSplitScreen: args.packageDocumentTypes.publishedMinutesOpenHtmlSplitScreen,
		PublishedMinutesClosedHtml: args.packageDocumentTypes.publishedMinutesClosedHtml,
		PublishedMinutesClosedHtmlSplitscreen: args.packageDocumentTypes.publishedMinutesClosedHtmlSplitScreen,

		AdoptedOpenMinutesPdf: args.packageDocumentTypes.adoptedOpenMinutesPdf,
		AdoptedClosedMinutesPdf: args.packageDocumentTypes.adoptedClosedMinutesPdf,
		AdoptedOpenMinutesHtml: args.packageDocumentTypes.adoptedOpenMinutesHtml,
		AdoptedClosedMinutesHtml: args.packageDocumentTypes.adoptedClosedMinutesHtml,
	};

	var localization = args.localization;

	var isIe = CivicWeb.Common.isIe();
	var includeMinutesAttachments = false;

	//Events
	var prevButtonClick = function () {
		var selectedGroup = $('.meeting-list-item-group-selected');
		var selectedGroupOrder = selectedGroup.attr('order');
		selectedGroupOrder--;
		var prevGroup = $('[order="' + selectedGroupOrder + '"]');
		if (prevGroup.length > 0) {
			selectedGroup.addClass('meeting-list-item-group').removeClass('meeting-list-item-group-selected');
			prevGroup.addClass('meeting-list-item-group-selected').removeClass('meeting-list-item-group');
			$(document.getElementById(nextButtonClientId)).show();
		}

		if ($('[order="' + --selectedGroupOrder + '"]').length === 0) {
			$(document.getElementById(prevButtonClientId)).hide();
		}
		else {
			$(document.getElementById(prevButtonClientId)).show();
		}
	};

	var nextButtonClick = function () {
		var selectedGroup = $('.meeting-list-item-group-selected');
		var selectedGroupOrder = selectedGroup.attr('order');
		selectedGroupOrder++;
		var nextGroup = $('[order="' + selectedGroupOrder + '"]');
		if (nextGroup.length > 0) {
			selectedGroup.addClass('meeting-list-item-group').removeClass('meeting-list-item-group-selected');
			nextGroup.addClass('meeting-list-item-group-selected').removeClass('meeting-list-item-group');
			$(document.getElementById(prevButtonClientId)).show();
		}

		if ($('[order="' + ++selectedGroupOrder + '"]').length === 0) {
			$(document.getElementById(nextButtonClientId)).hide();
		}
		else {
			$(document.getElementById(nextButtonClientId)).show();
		}
	};

	this.meetingClick = function (e, packageId, outputTypeId) {
		if (Number(packageId) > 0) {
			meetingId = packageId;

			$('#ExternalLink').hide();
			$('#ExternalMinutesLink').hide();
			$('#edit-external-links-popup').hide();

			$('.meeting-list-item-button-selected').addClass('meeting-list-item-button').removeClass('meeting-list-item-button-selected').attr({ 'aria-selected': 'false' });
			$(document.getElementById(e.id)).removeClass();
			$(document.getElementById(e.id)).addClass('meeting-list-item-button-selected background-color-hover').attr({ 'aria-selected': 'true' });
			$(document.getElementById(meetingInformationClientId)).attr({ 'aria-labelledby': e.id });
			locationItems = [];

			$(document.getElementById(agendaSplitScreenButtonClientId)).text(localization.splitscreenLabel).hide();
			$(document.getElementById('meeting-private-version-for')).addClass('hidden');
			$(document.getElementById(documentCoverPdfClientId)).hide();
			$('#print-version-label').hide();

			showDocumentLoading();

			$.ajax({
				url: '/Services/MeetingsService.svc/meetings/' + packageId.toString() + '/meetingDocuments',
				contentType: 'application/json', dataType: 'json', async: true, type: 'GET', cache: false, timeout: 30000,
				success: function (data) {
					var selectedDocumentId = meetingClickSuccess(data.Documents, data.MeetingDateFormatted, outputTypeId, data.MeetingIncludeMinutesAttachments, data.MeetingOnPublishShowDraftMinutes);
					checkMeetingForExternalLinks(packageId);
					if (purchasedVideo && packageId > 0 && selectedDocumentId > 0) {
						if (splitscreenLinkDocumentId > 0) {
							selectedDocumentId = splitscreenLinkDocumentId;
						}
						CivicWeb.Integration.Video.addVideoButtonToPortal(packageId, selectedDocumentId, $(document.getElementById(videoButtonIdClientId)));
					}
					else {
						$(document.getElementById(videoButtonIdClientId)).css('display', 'none');
					}
				},
				error: function () {
					hideDocumentLoading();
				}
			});
		}
	};

	var meetingClickSuccess = function (data, meetingDate, outputTypeId, meetingIncludeMinutesAttachments, meetingOnPublishShowDraftMinutes) {
		includeMinutesAttachments = meetingIncludeMinutesAttachments;
		$('.meeting-document-type-buttons').css('visibility', 'hidden');
		var currentSelectedDocumentId = 0;

		var iframe = $(document.getElementById(meetingDocumentClientId));
		var meetingDocumentUnpublished = $(document.getElementById(meetingDocumentUnpublishedClientId));

		iframe.parent().toggleClass('hidden', data.length === 0).parent().find('[data-type="meeting-links"]').toggleClass('hidden', data.length === 0);
		meetingDocumentUnpublished.toggleClass('hidden', data.length > 0);
		if (data.length > 0) {
			selectedAgenda = new Object();
			selectedMinutes = new Object();
			var splitscreenAgenda = {};
			var splitscreenMinutes = {};
			var closedFinalAgendaHtmlExists = false;

			for (var i = 0; i < data.length; i++) {
				document.getElementById(meetingTitleClientId).textContent = data[i].Name;
				$(document.getElementById(meetingDocumentClientId)).attr('title', data[i].Name);
				if (data[i].Type === meetingOutputType.Agenda) {
					if (data[i].DocumentType === packageDocumentType.PublishedAgendaClosedHtml || data[i].DocumentType === packageDocumentType.PublishedAgendaOpenHtml) {
						selectedAgenda.HtmlDocument = data[i];
						splitscreenAgenda = data[i];

						if (data[i].DocumentType === packageDocumentType.PublishedAgendaClosedHtml) {
							closedFinalAgendaHtmlExists = true;
						}
					}

					if (data[i].DocumentType === packageDocumentType.PublishedAgendaClosedPdf || data[i].DocumentType === packageDocumentType.PublishedAgendaOpenPdf) {
						selectedAgenda.PdfDocument = data[i];
					}

					if (data[i].DocumentType === packageDocumentType.PublishedAgendaClosedHtmlSplitScreen || data[i].DocumentType === packageDocumentType.PublishedAgendaOpenHtmlSplitScreen) {
						splitscreenAgenda = data[i];
					}
				}
				else if (data[i].Type === meetingOutputType.Minutes) {
					if (data[i].DocumentType === packageDocumentType.PublishedMinutesClosedHtml || data[i].DocumentType === packageDocumentType.PublishedMinutesOpenHtml || data[i].DocumentType === packageDocumentType.AdoptedOpenMinutesHtml) {
						selectedMinutes.HtmlDocument = data[i];
						splitscreenMinutes = data[i];
					}
					if (data[i].DocumentType === packageDocumentType.PublishedMinutesClosedPdf || data[i].DocumentType === packageDocumentType.PublishedMinutesOpenPdf) {
						selectedMinutes.PdfDocument = data[i];
					}
					else if (data[i].DocumentType === packageDocumentType.AdoptedClosedMinutesPdf || data[i].DocumentType === packageDocumentType.AdoptedOpenMinutesPdf) {
						selectedMinutes.PdfDocument = data[i];
					}
					if (data[i].DocumentType === packageDocumentType.PublishedMinutesClosedHtmlSplitscreen || data[i].DocumentType === packageDocumentType.PublishedMinutesOpenHtmlSplitScreen) {
						splitscreenMinutes = data[i];
					}
				}
			}

			if ((selectedAgenda.HtmlDocument || selectedAgenda.PdfDocument) && (outputTypeId === meetingOutputType.Agenda || outputTypeId === 0)) {
				var publicReleaseDelayDateString = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.PublicReleaseDelayDateString : selectedAgenda.PdfDocument.PublicReleaseDelayDateString;
				var agendaCover = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.AgendaCover : selectedAgenda.PdfDocument.AgendaCover;
				var isPublic = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.IsPublic : selectedAgenda.PdfDocument.IsPublic;
				$('#noPublicAccessWarning').remove();
				if (publicReleaseDelayDateString.length > 0 && isPublic) {
					$('.meeting-document-type-pdf-link, .agenda-splitscreen-button').hide();
					var noPublicAccessWarning = agendaCover + '<br/><br/>Public Release: ' + publicReleaseDelayDateString;
					iframe.addClass('hidden').before($('<span id="noPublicAccessWarning">').html('<span id="preview" title="Public Release: ' + publicReleaseDelayDateString + '"><span style="width: 100%; text-align: center; display:inline-table; background-color:white;"><div style="padding-top: 25px; font-weight:bold;">' + noPublicAccessWarning + '</div></span></body></html>'));
				}
				else {
					$('.meeting-document-type-pdf-link, .agenda-splitscreen-button').show();
					currentSelectedDocumentId = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.Id : selectedAgenda.PdfDocument.Id;
					showDocumentLoading(iframe.removeClass('hidden')).attr('src', '/document/' + currentSelectedDocumentId.toString() + `?lastModified=${selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.LastModified : selectedAgenda.PdfDocument.LastModified}`);
				}

				$(document.getElementById(minutesDocumentClientId)).removeClass('button-small-selected button-small').attr('aria-pressed', 'false');
				$(document.getElementById('collapse-minutes-button')).removeClass('selected-collapse-minutes-button').attr('aria-pressed', 'false');
				$(document.getElementById(agendaDocumentClientId)).removeClass('button-small-selected button-small').attr('aria-pressed', 'false');
				$(document.getElementById(agendaDocumentClientId)).addClass('button-small-selected').attr('aria-pressed', 'true');
				$(document.getElementById(minutesDocumentClientId)).addClass('button-small');

				if (selectedAgenda.HtmlDocument && selectedAgenda.HtmlDocument.MeetingId > 0) {
					$(document.getElementById(agendaSplitScreenButtonClientId)).removeClass('hidden');
					$(document.getElementById(agendaSplitScreenButtonClientId)).attr({ 'href': '/document/' + selectedAgenda.HtmlDocument.Id + '?splitscreen=true' + `&lastModified=${selectedAgenda.HtmlDocument.LastModified}` });
					if (closedFinalAgendaHtmlExists) {
						$(document.getElementById("annotate-agenda-button")).removeClass('hidden');
						$(document.getElementById("annotate-agenda-button")).attr({ 'href': '/home/meeting/document/' + selectedAgenda.HtmlDocument.MeetingId });
						$(document.getElementById('meeting-private-version-for')).removeClass('hidden');
					}
				}
				else {
					splitscreenLinkDocumentId = 0;
					$(document.getElementById(agendaSplitScreenButtonClientId)).addClass('hidden');
				}

				if (splitscreenMinutes && splitscreenMinutes.Id > 0) {
					selectedMinutes.SplitScreenDocument = splitscreenMinutes;
				}

				if (selectedAgenda.HtmlDocument && (outputTypeId === meetingOutputType.Agenda || outputTypeId === 0) && selectedAgenda.HtmlDocument.Format.toLowerCase() !== 'html') {
					$(document.getElementById(documentCoverPdfClientId)).show();
					$(document.getElementById(documentCoverPdfClientId)).attr({ 'href': '/document/' + selectedAgenda.HtmlDocument.Id + '/?printPdf=true' + `&lastModified=${selectedAgenda.HtmlDocument.LastModified}`, 'aria-label': localization.downloadAgendaLinkLabel }).text(localization.agendaLabel);
				}

				loadLocationItems(selectedAgenda.HtmlDocument ? Number(selectedAgenda.HtmlDocument.MeetingId) : Number(selectedAgenda.PdfDocument.MeetingId));
			}
			else if ((selectedMinutes.HtmlDocument || selectedMinutes.PdfDocument) && (outputTypeId === meetingOutputType.Minutes || outputTypeId === 0)) {
				currentSelectedDocumentId = selectedMinutes.HtmlDocument ? selectedMinutes.HtmlDocument.Id : selectedMinutes.PdfDocument.Id;
				showDocumentLoading(iframe).attr('src', '/document/' + currentSelectedDocumentId.toString() + `?lastModified=${selectedMinutes.HtmlDocument ? selectedMinutes.HtmlDocument.LastModified : selectedMinutes.PdfDocument.LastModified}`);
				var documentContents = isIe ? document.frames[meetingDocumentClientId].document : iframe.contents();
				iframe.height($(documentContents).height());

				$(document.getElementById(agendaDocumentClientId)).removeClass('button-small-selected button-small').attr('aria-pressed', 'false');
				$(document.getElementById(minutesDocumentClientId)).removeClass('button-small-selected button-small').attr('aria-pressed', 'false');

				$(document.getElementById(minutesDocumentClientId)).addClass('button-small-selected').attr('aria-pressed', 'true');
				$('#collapse-minutes-button.glyphicon-remove').addClass('selected-collapse-minutes-button');
				$(document.getElementById(agendaDocumentClientId)).addClass('button-small');

				if (selectedMinutes.HtmlDocument) {
					splitscreenLinkDocumentId = splitscreenMinutes.Id;
					selectedMinutes.SplitScreenDocument = splitscreenMinutes;
					$(document.getElementById(agendaSplitScreenButtonClientId)).removeClass('hidden');
					$(document.getElementById(agendaSplitScreenButtonClientId)).attr({ 'href': '/document/' + selectedMinutes.HtmlDocument.Id + '?splitscreen=true' + `&lastModified=${selectedMinutes.HtmlDocument.LastModified}` });
				}
				else {
					splitscreenLinkDocumentId = 0;
					$(document.getElementById(agendaSplitScreenButtonClientId)).addClass('hidden');
				}

				if (selectedMinutes.HtmlDocument && (outputTypeId === meetingOutputType.Minutes || outputTypeId === 0) && selectedMinutes.HtmlDocument.Format.toLowerCase() !== 'html') {
					$(document.getElementById(documentCoverPdfClientId)).show();
					$(document.getElementById(documentCoverPdfClientId)).attr({ 'href': '/document/' + selectedMinutes.HtmlDocument.Id + '/?printPdf=true' + `&lastModified=${selectedMinutes.HtmlDocument.LastModified}`, 'aria-label': localization.downloadMinutesLinkLabel }).text(localization.minutesLabel);
				}
			}

			$(document.getElementById("adopted-pdf-document")).addClass("hidden");
			$(document.getElementById("adopted-html-document")).addClass("hidden");
			$(document.getElementById("adopted-minutes-versions")).addClass("hidden");

			if (selectedAgenda.PdfDocument) {
				$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedAgenda.PdfDocument.Id.toString() + `?lastModified=${selectedAgenda.PdfDocument.LastModified}`, 'aria-label': localization.downloadFullAgendaLinkLabel }).text(localization.agendaLabel + ' ' + localization.packageLabel);
				$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
			}
			else if (selectedAgenda.HtmlDocument) {
				$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedAgenda.HtmlDocument.Id + `?lastModified=${selectedAgenda.HtmlDocument.LastModified}`, 'aria-label': localization.downloadAgendaLinkLabel }).text(localization.agendaLabel + ' ' + localization.packageLabel);
				$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
			}
			else if (selectedMinutes.PdfDocument) {
				if (selectedMinutes.PdfDocument.DocumentType === packageDocumentType.AdoptedClosedMinutesPdf || selectedMinutes.PdfDocument.DocumentType === packageDocumentType.AdoptedOpenMinutesPdf) {
					$(document.getElementById("adopted-pdf-document")).attr('href', '/document/' + selectedMinutes.PdfDocument.Id.toString() + `?lastModified=${selectedMinutes.PdfDocument.LastModified}`).removeClass("hidden");
					$(document.getElementById("adopted-html-document")).attr('href', '/document/' + selectedMinutes.PdfDocument.Html + `?lastModified=${selectedMinutes.PdfDocument.LastModified}`).removeClass("hidden");
					$(document.getElementById("adopted-minutes-versions")).removeClass("hidden");
				}
				else {
					$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedMinutes.PdfDocument.Id.toString() + `?lastModified=${selectedMinutes.PdfDocument.LastModified}`, 'aria-label': localization.downloadFullMinutesLinkLabel }).text(localization.minutesLabel + ' ' + localization.packageLabel);
					$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
				}
			}
			else if (selectedMinutes.HtmlDocument) {
				$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedMinutes.HtmlDocument.Id + `?lastModified=${selectedMinutes.HtmlDocument.LastModified}`, 'aria-label': localization.downloadMinutesLinkLabel }).text(localization.minutesLabel + ' ' + localization.packageLabel);
				$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
			}
			else {
				$(document.getElementById(documentPrintVersionClientId)).addClass('hidden');
			}

			$(document.getElementById(editExternalLinksClientId)).show();

			$(document.getElementById(minutesDocumentClientId)).addClass('hidden');
			$(document.getElementById(agendaDocumentClientId)).addClass('hidden');
			$(document.getElementById("live-meeting")).addClass("hidden");
			$(document.getElementById('collapse-minutes-button')).addClass('hidden');
			if (selectedMinutes.HtmlDocument || selectedMinutes.PdfDocument) {
				$(document.getElementById(minutesDocumentClientId)).removeClass('hidden');
				$(document.getElementById('remove-minutes')).removeClass('hidden');
				if (hasPortalUpdate) {
					$(document.getElementById('collapse-minutes-button')).removeClass('hidden');
				}
			}

			if (selectedAgenda.HtmlDocument || selectedAgenda.PdfDocument) {
				$(document.getElementById(agendaDocumentClientId)).removeClass('hidden');
			}

			if ($(document.getElementById(documentPrintVersionClientId)).is(':visible') || $(document.getElementById(documentCoverPdfClientId)).is(':visible')) {
				$('#print-version-label').show();
			}

			if (history && history.pushState) {
				changeUrl(data[0].MeetingId);
			}
		}
		else {
			selectedAgenda = new Object();
			selectedMinutes = new Object();
			$(document.getElementById('map')).hide();
			$(document.getElementById(documentPrintVersionClientId)).addClass('hidden');
			$(document.getElementById(editExternalLinksClientId)).hide();
			meetingDocumentUnpublished.html(localization.labelTheMeetingAgendaIsCurrentlyUnderRevision.replace('{0}', meetingDate));
		}

		if (meetingId > 0) {
			$.ajax({
				url: '/Services/MeetingsService.svc/meetings/' + meetingId.toString() + '/meetingData',
				contentType: 'application/json', dataType: 'json', async: true, type: 'GET', cache: false, timeout: 30000,
				success: function (meetingData) {
					currentMeetingData = meetingData;
					document.getElementById(meetingTitleClientId).textContent = currentMeetingData.Name;

					$(document.getElementById('meeting-location')).text(currentMeetingData.Location);
					$(document.getElementById('meeting-location-container')).toggleClass('hidden', !currentMeetingData.Location);

					$(document.getElementById('meeting-time')).text(currentMeetingData.Time);
					$(document.getElementById('meeting-time-container')).toggleClass('hidden', !currentMeetingData.Time);

					$(document.getElementById(requestToSpeakClientId)).attr({ 'data-id': meetingId, 'data-back': selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.Id : (selectedAgenda.PdfDocument ? selectedAgenda.PdfDocument.Id : undefined) }).off('click').on('click', requestToSpeakClick).closest('div')
						.toggleClass('hidden', currentMeetingData.InPast);

					if (!currentMeetingData.Historic && currentMeetingData.Live) {
						$(document.getElementById("live-meeting")).off("click").on("click", function () { window.location.href = "/home/public/meeting/document/" + meetingId });
						$(document.getElementById("live-meeting")).removeClass("hidden");
					}

					reloadMembers(meetingData.Members);
				}
			});
		}
		$('.meeting-document-type-buttons').css('visibility', 'visible');

		if (viewMinutes && !$(document.getElementById(minutesDocumentClientId)).hasClass('hidden')) {
			setTimeout(function () { $(document.getElementById(minutesDocumentClientId)).click(); }, 0);
		}

		return currentSelectedDocumentId;
	};

	var reloadMembers = function (members) {
		var list = $(document.getElementById(membersListClientId)).find('ol').empty();

		if (!members) {
			return;
		}

		members.forEach(function (member) {
			list.append($('<li></li>').text(member));
		});
	}

	var videoButtonClick = function () {
		CivicWeb.Common.Instrumentation.recordAction('viewPortalMeetingVideo');
	};

	var applyButtonClick = function () {
		var meetingTypeId = $(this).attr('data-meetingtype-id');
		var trackerWindow;
		var windowJquery;
		if (boardApplicationTrackers && boardApplicationTrackers.length > 1 && $('#board-application-trackers option').length === 1) {

			var boardApplicationTrackersSelect = $(document.getElementById('board-application-trackers')).attr({ 'data-meetingtype-id': meetingTypeId });
			$(document.getElementById('board-application-select-container')).removeClass('hidden');
			for (var i = 0; i < boardApplicationTrackers.length; i++) {
				var tracker = boardApplicationTrackers[i];
				boardApplicationTrackersSelect.append($('<option>', { 'value': tracker.id }).html(tracker.name));
			}

			trackerWindow = window.$find(trackerWindowClientId);
			if (trackerWindow) {
				$('#trackerWindowClientId').find('iframe').remove();
				windowJquery = $(window);
				trackerWindow.set_height(Math.max(windowJquery.height() * 0.9, 600));
				trackerWindow.set_width(720);
				trackerWindow.show();
			}
		}
		else if (boardApplicationTrackers && boardApplicationTrackers.length > 0) {
			$(document.getElementById('board-application-select-container')).addClass('hidden');
			var trackerId = boardApplicationTrackers[0].id;
			trackerWindow = window.$find(trackerWindowClientId);
			if (trackerWindow) {
				windowJquery = $(window);
				trackerWindow.set_height(Math.max(windowJquery.height() * 0.9, 600));
				trackerWindow.set_width(720);
				trackerWindow.setUrl('/Items/Item/public.aspx?TypeId=' + trackerId.toString() + '&mtId=' + meetingTypeId.toString());
				trackerWindow.show();
			}
		}
	};

	var boardApplicationTrackerSelectChange = function () {
		var meetingTypeId = $(document.getElementById('board-application-trackers')).attr('data-meetingtype-id');
		var trackerId = $(document.getElementById('board-application-trackers')).val();
		var trackerWindow = window.$find(trackerWindowClientId);
		if (trackerId > 0 && trackerWindow) {
			var windowJquery = $(window);
			trackerWindow.set_height(Math.max(windowJquery.height() * 0.9, 600));
			trackerWindow.set_width(720);
			trackerWindow.setUrl('/Items/Item/public.aspx?TypeId=' + trackerId.toString() + '&mtId=' + meetingTypeId.toString());
			$(document.getElementById('board-application-select-container')).addClass('hidden');
		}
	};

	this.PortalCloseRadTrackerWindow = function () {
		var trackerWindow = window.$find(trackerWindowClientId);
		if (trackerWindow) {
			trackerWindow.setUrl('/Global/Images/indicator_medium.gif');
		}
	};

	var minutesLinkUrlBlur = function (e) {
		setMinutesLinkOptions(e.target);
	};

	var externalLinkUrlBlur = function (e) {
		setExternalLinkOptions(e.target);
	};

	var saveExternalLinksClick = function () {
		var button = $(this);
		CivicWeb.Common.Button.update(button, localization.savingButtonLabel, true, true);
		saveExternalLinks(function () {
			CivicWeb.Common.Button.update(button, localization.saveButtonLabel, false, false);
		});
	};

	var uploadMinutesClick = function () {
		$(document.getElementById('upload-minutes-select')).click();
	};

	var uploadMinutesSelectChange = function () {
		var fileSelector = document.getElementById('upload-minutes-select');
		var file = fileSelector && fileSelector.files && fileSelector.files.length ? fileSelector.files[0] : null;
		if (meetingId > 0 && file) {
			var fileData = new FormData();
			fileData.append(file.name, file);

			var progressBar = $('<div></div>').attr({ 'class': 'progress-bar progress-bar-success progress-bar-striped active', 'role': 'progressbar', 'aria-valuenow': '0', 'aria-valuemin': '0', 'aria-valuemax': '100' }).css({ 'width': '3%' }).text('0%');
			var progressRow = $('<div></div>').attr({ 'class': 'minutes-document', 'data-name': file.name })
				.append($('<div></div>').attr({ 'class': 'progress' }).append(progressBar));

			$(document.getElementById(uploadMinutesClientId)).before(progressRow);

			$.ajax({
				url: '/api/meeting/' + meetingId + '/uploadportalminutes',
				contentType: false,
				dataType: 'json',
				async: true,
				cache: false,
				type: 'POST',
				data: fileData,
				processData: false,
				xhr: function () {
					var progressListener = function (e) {
						if (e.lengthComputable) {
							var percentage = Math.round(e.loaded / e.total * 90);

							progressBar.attr({ 'aria-valuenow': percentage.toString() }).css({ 'width': percentage.toString() + '%' }).text(percentage.toString() + '%');
						}
					};

					// ReSharper disable once InconsistentNaming
					var xmlHttpRequest = new XMLHttpRequest();

					//Download progress
					if (xmlHttpRequest.addEventListener) {
						// ReSharper disable once Html.EventNotResolved
						xmlHttpRequest.addEventListener('progress', progressListener, false);
					}
					if (xmlHttpRequest.upload && xmlHttpRequest.upload.addEventListener) {
						// ReSharper disable once Html.EventNotResolved
						xmlHttpRequest.upload.addEventListener('progress', progressListener, false);
					}

					return xmlHttpRequest;
				}
			})
				.done(function () {
					progressBar.attr({ 'aria-valuenow': '100' }).css({ 'width': '100%' }).text('100% - ' + file.name);
					setTimeout(function () { $('button.meeting-list-item-button-selected:visible').click(); }, 2000);
				})
				.fail(function () {
					progressBar.removeClass('progress-bar-success').addClass('progress-bar-danger').attr({ 'aria-valuenow': '100' }).css({ 'width': '100%' }).text(localization.labelUploadFailed);
				})
				.always(function () {
					setTimeout(function () {
						progressRow.remove();
					}, 3000);
				});
		}
	};

	var removeMinutesClick = function () {
		CivicWeb.Common.Notification.hide('minutes-notification');
		CivicWeb.Common.Button.update($(document.getElementById('remove-minutes')), localization.labelProcessing, true, true);
		$.ajax({
			url: '/api/meeting/' + meetingId + '/unpublish',
			contentType: 'application/json',
			dataType: 'json',
			async: true,
			cache: false,
			type: 'POST',
			data: JSON.stringify({ agenda: false })
		})
			.done(function () {
				$(document.getElementById('remove-minutes')).addClass('hidden');
				CivicWeb.Common.Notification.show('minutes-notification', CivicWeb.Common.Notification.types.success, localization.notificationSuccess);
				setTimeout(function () { $('button.meeting-list-item-button-selected:visible').click(); }, 2000);
			})
			.fail(function () {
				CivicWeb.Common.Notification.show('minutes-notification', CivicWeb.Common.Notification.types.error, localization.notificationFailed);
			})
			.always(function () {
				CivicWeb.Common.Button.update($(document.getElementById('remove-minutes')), localization.removeMinutesButton, false, false);
			});
	};

	var requestToSpeakClick = function (e) {
		var button = $(e.target).closest('button');
		var meetingId = button.attr('data-id');

		var viewportWidth = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
		if (viewportWidth < 600) {
			window.location.href = '/home/public/requesttospeak/' + meetingId;
		}
		else {
			var backId = button.attr('data-back');
			$('iframe#' + meetingDocumentClientId)
				.attr({ 'src': '/home/public/requesttospeak/' + meetingId + '?backId=' + backId });
		}

		e.preventDefault();
	};

	//#region External links
	var setMinutesLinkOptions = function (linkUrlElement) {
		return setLinkOptions(linkUrlElement, 'external-minutes-target-meeting');
	}

	var setExternalLinkOptions = function (linkUrlElement) {
		return setLinkOptions(linkUrlElement, 'external-target-meeting');
	}

	var setLinkOptions = function (linkUrlElement, externalTargetClientId) {
		linkUrlElement = $(linkUrlElement);
		var link = linkUrlElement.val();
		var localLink = isLocalLink(link);

		var radioButton = $(document.getElementById(externalTargetClientId)).add('label[for="' + externalTargetClientId + '"]').prop('disabled', !localLink);
		if (!localLink) {
			radioButton.prop('checked', false);
		}

		return linkUrlElement;
	}

	var isLocalLink = function (link) {
		link = link || '';

		return link.indexOf('/') === 0 && link.indexOf('//') !== 0 ||
			link.indexOf('https://' + window.location.hostname) === 0 ||
			link.indexOf('http://' + window.location.hostname) === 0 ||
			link.indexOf('//' + window.location.hostname) === 0;
	};

	var showDocumentLoading = function (iframe) {
		iframe = iframe || $(document.getElementById(meetingDocumentClientId));

		var loadingOverlay = document.getElementById(meetingDocumentLoadingClientId);
		if (!loadingOverlay) {
			iframe
				.before($('<div></div>').attr({ 'id': meetingDocumentLoadingClientId, 'class': 'throbber-overlay throbber-large throbber-background-white hidden' })
					.append(CivicWeb.Common.Button.getThrobber()));

			loadingOverlay = document.getElementById(meetingDocumentLoadingClientId);
		}
		loadingOverlay = $(loadingOverlay);

		loadingOverlay.css({ 'top': iframe.position().top + 'px', 'left': iframe.position().left + 'px', 'width': iframe.outerWidth() + 'px', height: iframe.outerHeight() + 'px' }).removeClass('hidden');

		return iframe;
	};

	var hideDocumentLoading = function () {
		$(document.getElementById(meetingDocumentLoadingClientId)).addClass('hidden');
	};

	var checkMeetingForExternalLinks = function (packageId) {
		if (packageId > 0) {
			$.ajax({
				url: '/Services/MeetingsService.svc/meetings/' + packageId.toString() + '/meetingData',
				contentType: 'application/json', dataType: 'json', async: true, type: 'GET', cache: false, timeout: 30000,
				success: function (meetingData) {
					currentMeetingData = meetingData;
					loadExternalLinks(meetingData);
				}
			});
		}
	};

	var loadExternalLinks = function (meetingData) {
		loadExternalLink(meetingData);
		loadExternalMinutesLink(meetingData);
	};

	var loadExternalLink = function (meetingData) {
		//Set external link data
		if (meetingData.MeetingExternalLinkUrl && meetingData.MeetingExternalLinkUrl.length > 0) {
			var hyperlink = meetingData.MeetingExternalLinkUrl;
			var target = meetingData.MeetingExternalLinkTarget == null ? '_blank' : meetingData.MeetingExternalLinkTarget;
			var localLink = isLocalLink(hyperlink);
			if (hyperlink.indexOf('http://') === -1 && hyperlink.indexOf('https://') === -1 && hyperlink.indexOf('//') === -1 && !localLink) {
				hyperlink = 'http://' + hyperlink;
			}

			$(document.getElementById('ExternalLink')).off('click');
			if (target === 'popUpWindow') {
				$(document.getElementById('ExternalLink')).on('click', function (e) { openLinkInPopup(hyperlink); e.preventDefault(); });
			}
			if (target === 'MeetingDocument' && localLink) {
				$('#ExternalLink').on('click', function (e) {
					$('iframe#' + meetingDocumentClientId).height('60em');
					$('iframe#' + meetingDocumentClientId).attr({ 'src': hyperlink });

					$('#' + minutesDocumentClientId).removeClass('button-small-selected').attr('aria-pressed', 'false');
					$('#' + agendaDocumentClientId).removeClass('button-small-selected').attr('aria-pressed', 'false');
					$('#ExternalLink').removeClass('button-small');
					$('#ExternalMinutesLink').removeClass('button-small-selected').attr('aria-pressed', 'false');

					$('#ExternalLink').addClass('button-small-selected').attr('aria-pressed', 'true');
					$('#ExternalMinutesLink').addClass('button-small');
					$('#' + agendaDocumentClientId).addClass('button-small');
					$('#' + minutesDocumentClientId).addClass('button-small');
					$('#' + documentPrintVersionClientId).addClass('hidden');

					e.preventDefault();
				});
			}
			else {
				target = '_blank';
			}
			$(document.getElementById('ExternalLink')).attr({ 'href': hyperlink, 'target': target }).text(meetingData.MeetingExternalLinkName);
			$(document.getElementById('ExternalLink')).show();
		}
		else {
			$(document.getElementById('ExternalLink')).hide();
		}
	};

	var loadExternalMinutesLink = function (meetingData) {
		//Set external minutes link data if there is no minutes
		if (!selectedMinutes || !selectedMinutes.HtmlDocument && !selectedMinutes.PdfDocument || meetingData.MeetingExternalMinutesLinkUrl && meetingData.MeetingExternalMinutesLinkUrl.length > 0) {
			if (meetingData.MeetingExternalMinutesLinkUrl && meetingData.MeetingExternalMinutesLinkUrl.length > 0) {
				var minutesHyperlink = meetingData.MeetingExternalMinutesLinkUrl;
				var minutesTarget = !meetingData.MeetingExternalMinutesLinkTarget ? 'MeetingDocument' : meetingData.MeetingExternalMinutesLinkTarget;
				var localLink = isLocalLink(minutesHyperlink);
				if (minutesHyperlink.indexOf('http://') === -1 && minutesHyperlink.indexOf('https://') === -1 && minutesHyperlink.indexOf('//') === -1 && !localLink) {
					minutesHyperlink = 'http://' + minutesHyperlink;
				}
				$(document.getElementById('ExternalMinutesLink')).off('click');
				if (minutesTarget === 'popUpWindow') {
					$(document.getElementById('ExternalMinutesLink')).off('click').on('click', function (e) { openLinkInPopup(minutesHyperlink); e.preventDefault(); });
				}
				if (minutesTarget === 'MeetingDocument') {
					$(document.getElementById('ExternalMinutesLink')).on('click', function (e) {
						var meetingDocument = $(document.getElementById(meetingDocumentClientId));
						meetingDocument.height('60em');
						showDocumentLoading(meetingDocument).attr({ 'src': minutesHyperlink });

						$(document.getElementById(minutesDocumentClientId)).removeClass('button-small-selected').attr('aria-pressed', 'false');
						$(document.getElementById('collapse-minutes-button')).removeClass('selected-collapse-minutes-button');
						$(document.getElementById(agendaDocumentClientId)).removeClass('button-small-selected').attr('aria-pressed', 'false');
						$(document.getElementById('ExternalLink')).removeClass('button-small-selected').attr('aria-pressed', 'false');
						$(document.getElementById('ExternalMinutesLink')).removeClass('button-small');

						$(document.getElementById('ExternalMinutesLink')).addClass('button-small-selected').attr('aria-pressed', 'true');
						$(document.getElementById('ExternalLink')).addClass('button-small');
						$(document.getElementById(agendaDocumentClientId)).addClass('button-small');
						$(document.getElementById(minutesDocumentClientId)).addClass('button-small');
						$(document.getElementById(documentPrintVersionClientId)).addClass('hidden');

						if (!selectedMinutes.HtmlDocument && !selectedMinutes.PdfDocument) {
							$(document.getElementById(minutesDocumentClientId)).addClass('hidden');
						}

						e.preventDefault();
					});
				}
				else {
					minutesTarget = '_blank';
				}
				$(document.getElementById('ExternalMinutesLink')).attr({ 'href': minutesHyperlink, 'target': minutesTarget }).text(meetingData.MeetingExternalMinutesLinkName);
				$(document.getElementById('ExternalMinutesLink')).show();
				$(document.getElementById('AddNewExternalMinutesLink')).hide();

				if (selectedMinutes && (selectedMinutes.HtmlDocument || selectedMinutes.PdfDocument)) {
					$(document.getElementById(minutesDocumentClientId)).addClass('hidden');
				}
			}
		}
	};

	var setExternalLink = function (meetingData) {
		var externalLinkUrl = $('#external-link-url');
		var externalLinkName = $('#external-link-text');
		var url = externalLinkUrl.val();
		var name = externalLinkName.val();
		externalLinkUrl.removeClass('invalid');
		externalLinkName.removeClass('invalid');
		externalLinkName.parent().find('data-required').remove();
		if (url.length > 0 && name.length > 0) {
			meetingData.MeetingExternalLinkUrl = url;
			meetingData.MeetingExternalLinkName = name;
			meetingData.MeetingExternalLinkTarget = $('input[name="externalLinkTarget"]:checked').val();
		}
		else {
			if (name.length > 0 && url.length === 0) {
				externalLinkUrl.addClass('invalid');
				return false;
			}
			else if (url.length > 0 && name.length === 0) {
				externalLinkName.addClass('invalid');
				return false;
			}
		}

		setExternalLinkOptions(externalLinkUrl);

		return true;
	};

	var setExternalMinutesLink = function (meetingData) {
		var externalLinkUrl = $(document.getElementById('external-minutes-link-url'));
		var externalLinkName = $(document.getElementById('external-minutes-link-text'));
		var url = externalLinkUrl.val();
		var name = externalLinkName.val();
		externalLinkUrl.removeClass('invalid');
		externalLinkName.removeClass('invalid');
		if (url.length > 0 && name.length > 0) {
			meetingData.MeetingExternalMinutesLinkUrl = url;
			meetingData.MeetingExternalMinutesLinkName = name;
			meetingData.MeetingExternalMinutesLinkTarget = $('input[name="externalMinutesLinkTarget"]:checked').val();
		}
		else {
			if (name.length > 0 && url.length === 0) {
				externalLinkUrl.addClass('invalid');
				return false;
			}
			else if (url.length > 0 && name.length === 0) {
				externalLinkName.addClass('invalid');
				return false;
			}
		}

		setMinutesLinkOptions(externalLinkUrl);

		return true;
	};

	var saveExternalLinks = function (callback) {
		if (currentMeetingData.Id > 0 && setExternalLink(currentMeetingData) && setExternalMinutesLink(currentMeetingData)) {
			$.ajax({
				url: '/Services/MeetingsService.svc/meetings/' + currentMeetingData.Id.toString() + '/save',
				contentType: 'application/json', dataType: 'json', async: true, type: 'POST', cache: false, timeout: 30000, data: JSON.stringify(currentMeetingData),
				success: function () {
					loadExternalLinks(currentMeetingData);
					$('#edit-external-links-popup').hide();
					$('#MeetingDocumentContainer').show();

					if (callback) {
						callback();
					}
				}
			});
		}
		else {
			CivicWeb.Common.Button.update($(document.getElementById('save-external-links')), localization.saveButtonLabel, false, false);
		}
	};

	var openLinkInPopup = function (hyperlink) {
		window.open(hyperlink, '_blank', 'toolbar=0,location=0,directories=0,status=0,menubar=0,scrollbars=1,resizable=1,width=950,height=650');
	};

	var deleteExternalLinkClick = function () {
		var button = $(this);
		var minutes = button.attr('data-type') === 'minutes';
		CivicWeb.Common.Button.update($(this), localization.deletingButtonLabel, true, true);
		if (minutes) {
			currentMeetingData.MeetingExternalMinutesLinkUrl = '';
			currentMeetingData.MeetingExternalMinutesLinkName = '';
			currentMeetingData.MeetingExternalMinutesLinkTarget = '';
			$(document.getElementById('external-minutes-link-url')).val('');
			$(document.getElementById('external-minutes-link-text')).val('');
			$('#ExternalMinutesLink').hide();

			setMinutesLinkOptions(document.getElementById('external-minutes-link-url'));
		}
		else {
			currentMeetingData.MeetingExternalLinkUrl = '';
			currentMeetingData.MeetingExternalLinkName = '';
			currentMeetingData.MeetingExternalLinkTarget = '';
			$(document.getElementById('external-link-url')).val('');
			$(document.getElementById('external-link-text')).val('');
			$('#ExternalLink').hide();

			setExternalLinkOptions(document.getElementById('external-link-url'));
		}

		saveExternalLinks(function () {
			CivicWeb.Common.Button.update(button, localization.deleteButtonLabel, false, false);
		});
	};

	var editExternalLinksClick = function () {
		if (currentMeetingData.MeetingExternalMinutesLinkName && currentMeetingData.MeetingExternalMinutesLinkName.length) {
			$(document.getElementById('external-minutes-link-url')).val(currentMeetingData.MeetingExternalMinutesLinkUrl);
			$(document.getElementById('external-minutes-link-text')).val(currentMeetingData.MeetingExternalMinutesLinkName);
			$('input[name="externalMinutesLinkTarget"][value="' + currentMeetingData.MeetingExternalMinutesLinkTarget + '"]').prop('checked', true);

			setMinutesLinkOptions(document.getElementById('external-minutes-link-url'));
		}

		if (currentMeetingData.MeetingExternalLinkUrl && currentMeetingData.MeetingExternalLinkUrl.length) {
			$(document.getElementById('external-link-url')).val(currentMeetingData.MeetingExternalLinkUrl);
			$(document.getElementById('external-link-text')).val(currentMeetingData.MeetingExternalLinkName);
			$('input[name="externalLinkTarget"][value="' + currentMeetingData.MeetingExternalLinkTarget + '"]').prop('checked', true);

			setExternalLinkOptions(document.getElementById('external-link-url'));
		}

		$(document.getElementById('MeetingDocumentContainer')).hide();
		$(document.getElementById('edit-external-links-popup')).removeClass('hidden').show();
	};
	//#endregion

	this.meetingDocumentTypeClick = function (type) {
		$(document.getElementById('map')).hide();
		$(document.getElementById(agendaShowMapButtonClientId)).hide();
		$(document.getElementById(agendaHideMapButtonClientId)).hide();
		$(document.getElementById('MeetingDocumentContainer')).show();
		$(document.getElementById(documentCoverPdfClientId)).hide();
		$(document.getElementById("adopted-pdf-document")).addClass("hidden");
		$(document.getElementById("adopted-html-document")).addClass("hidden");
		$(document.getElementById("adopted-minutes-versions")).addClass("hidden");

		if (type === meetingOutputType.Agenda && selectedAgenda) {
			if (selectedAgenda.HtmlDocument || selectedAgenda.PdfDocument) {
				var publicReleaseDelayDateString = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.PublicReleaseDelayDateString : selectedAgenda.PdfDocument.PublicReleaseDelayDateString;
				var agendaCover = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.AgendaCover : selectedAgenda.PdfDocument.AgendaCover;
				var isPublic = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.IsPublic : selectedAgenda.PdfDocument.IsPublic;

				$(document.getElementById('noPublicAccessWarning')).remove();
				if (publicReleaseDelayDateString.length > 0 && isPublic) {
					var noPublicAccessWarning = agendaCover + '<br/><br/>Public Release: ' + publicReleaseDelayDateString;
					$('.meeting-document-type-pdf-link, .agenda-splitscreen-button').hide();
					$(document.getElementById(meetingDocumentClientId)).addClass('hidden').before($('<span id="noPublicAccessWarning">').html('<span id="preview" title="Public Release: ' + publicReleaseDelayDateString + '"><span style="width: 100%; text-align: center; display:inline-table; background-color:white;"><div style="padding-top: 25px; font-weight:bold;">' + noPublicAccessWarning + '</div></span></body></html>'));
				}
				else {
					$('.meeting-document-type-pdf-link, .agenda-splitscreen-button').show();

					var currentSelectedDocumentId = selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.Id : selectedAgenda.PdfDocument.Id;
					showDocumentLoading($(document.getElementById(meetingDocumentClientId)).removeClass('hidden')).attr('src', '/document/' + currentSelectedDocumentId.toString() + `?lastModified=${selectedAgenda.HtmlDocument ? selectedAgenda.HtmlDocument.LastModified : selectedAgenda.PdfDocument.LastModified}`);
				}

				$(document.getElementById(minutesDocumentClientId)).removeClass('button-small-selected').attr('aria-pressed', 'false');
				$(document.getElementById('collapse-minutes-button')).find('.glyphicon-remove').removeClass('selected-collapse-minutes-button');
				$(document.getElementById(agendaDocumentClientId)).removeClass('button-small');
				$(document.getElementById('ExternalMinutesLink')).removeClass('button-small-selected').attr('aria-pressed', 'false');
				$(document.getElementById('ExternalLink')).removeClass('button-small-selected').attr('aria-pressed', 'false');

				$(document.getElementById(minutesDocumentClientId)).addClass('button-small');
				$(document.getElementById(agendaDocumentClientId)).addClass('button-small-selected').attr('aria-pressed', 'true');
				$(document.getElementById('ExternalMinutesLink')).addClass('button-small');
				$(document.getElementById('ExternalLink')).addClass('button-small');

				if (locationItems.length > 0) {
					$(document.getElementById(agendaShowMapButtonClientId)).show();
				}

				if (selectedAgenda.HtmlDocument && selectedAgenda.HtmlDocument.Format.toLowerCase() !== 'html') {
					$(document.getElementById(documentCoverPdfClientId)).show();
					$(document.getElementById(documentCoverPdfClientId)).attr('href', '/document/' + selectedAgenda.HtmlDocument.Id + '/?printPdf=true' + `&lastModified=${selectedAgenda.HtmlDocument.LastModified}`).text(localization.agendaLabel);

					$(document.getElementById(agendaSplitScreenButtonClientId)).attr({ 'href': '/document/' + selectedAgenda.HtmlDocument.Id + '?splitscreen=true' });
					$(document.getElementById(agendaSplitScreenButtonClientId)).removeClass('hidden');
				}
				else {
					$(document.getElementById(agendaSplitScreenButtonClientId)).addClass('hidden');
				}
			}

			if (selectedAgenda.PdfDocument) {
				$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedAgenda.PdfDocument.Id + `?lastModified=${selectedAgenda.PdfDocument.LastModified}`, 'aria-label': localization.downloadFullAgendaLinkLabel }).text(localization.agendaLabel + ' ' + localization.packageLabel);
				$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
			}
			else if (selectedAgenda.HtmlDocument) {
				$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedAgenda.HtmlDocument.Id + `?lastModified=${selectedAgenda.HtmlDocument.LastModified}`, 'aria-label': localization.downloadAgendaLinkLabel }).text(localization.agendaLabel + ' ' + localization.packageLabel);
				$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
			}
			else {
				$(document.getElementById(documentPrintVersionClientId)).addClass('hidden');
			}

			if (!selectedMinutes.HtmlDocument && !selectedMinutes.PdfDocument) {
				$(document.getElementById(minutesDocumentClientId)).addClass('hidden');
			}
		}
		else if (type === meetingOutputType.Minutes && selectedMinutes) {
			if (selectedMinutes.HtmlDocument || selectedMinutes.PdfDocument) {
				$('#noPublicAccessWarning').remove();
				$('.meeting-document-type-pdf-link, .agenda-splitscreen-button').show();

				showDocumentLoading($(document.getElementById(meetingDocumentClientId)).removeClass('hidden')).attr('src', '/document/' + (selectedMinutes.HtmlDocument ? selectedMinutes.HtmlDocument.Id : selectedMinutes.PdfDocument.Id).toString() + `?lastModified=${selectedMinutes.HtmlDocument ? selectedMinutes.HtmlDocument.LastModified : selectedMinutes.PdfDocument.LastModified}`);

				$(document.getElementById(agendaDocumentClientId)).removeClass('button-small-selected').attr('aria-pressed', 'false');
				$(document.getElementById(minutesDocumentClientId)).removeClass('button-small');
				$('#ExternalMinutesLink').removeClass('button-small-selected').attr('aria-pressed', 'false');
				$('#ExternalLink').removeClass('button-small-selected').attr('aria-pressed', 'false');

				$(document.getElementById(agendaDocumentClientId)).addClass('button-small');
				$(document.getElementById(minutesDocumentClientId)).addClass('button-small-selected').attr('aria-pressed', 'true');
				$('#collapse-minutes-button.glyphicon-remove').addClass('selected-collapse-minutes-button');

				$('#ExternalMinutesLink').addClass('button-small');
				$('#ExternalLink').addClass('button-small');

				if (selectedMinutes.HtmlDocument && selectedMinutes.HtmlDocument.Format.toLowerCase() !== 'html') {
					$(document.getElementById(documentCoverPdfClientId)).show();
					$(document.getElementById(documentCoverPdfClientId)).attr({ 'href': '/document/' + selectedMinutes.HtmlDocument.Id + '/?printPdf=true' + `&lastModified=${selectedMinutes.HtmlDocument.LastModified}`, 'aria-label': localization.downloadMinutesLinkLabel }).text(localization.minutesLabel);

					$(document.getElementById(agendaSplitScreenButtonClientId)).attr({ 'href': '/document/' + selectedMinutes.HtmlDocument.Id + '?splitscreen=true' + `&lastModified=${selectedMinutes.HtmlDocument.LastModified}` });
					$(document.getElementById(agendaSplitScreenButtonClientId)).removeClass('hidden');
				}
				else {
					$(document.getElementById(agendaSplitScreenButtonClientId)).addClass('hidden');
				}
			}

			if (selectedMinutes.PdfDocument) {
				if (selectedMinutes.PdfDocument.DocumentType === packageDocumentType.AdoptedClosedMinutesPdf || selectedMinutes.PdfDocument.DocumentType === packageDocumentType.AdoptedOpenMinutesPdf) {
					$(document.getElementById(documentPrintVersionClientId)).addClass('hidden');
					$(document.getElementById(documentCoverPdfClientId)).hide();
					$('#print-version-label').hide();

					$(document.getElementById("adopted-pdf-document")).attr({ 'href': '/document/' + selectedMinutes.PdfDocument.Id.toString() + `?lastModified=${selectedMinutes.PdfDocument.LastModified}`, 'aria-label': localization.downloadFullMinutesLinkLabel }).removeClass("hidden");
					$(document.getElementById("adopted-html-document")).attr({ 'href': '/document/' + selectedMinutes.PdfDocument.Html + `?lastModified=${selectedMinutes.PdfDocument.LastModified}`, 'aria-label': localization.downloadMinutesLinkLabel }).removeClass("hidden");
					$(document.getElementById("adopted-minutes-versions")).removeClass("hidden");
				}
				else {
					$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedMinutes.PdfDocument.Id + `?lastModified=${selectedMinutes.PdfDocument.LastModified}`, 'aria-label': localization.downloadFullMinutesLinkLabel }).text(localization.minutesLabel + ' ' + localization.packageLabel);
					$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
				}
			}
			else if (selectedMinutes.HtmlDocument) {
				$(document.getElementById(documentPrintVersionClientId)).attr({ 'href': '/document/' + selectedMinutes.HtmlDocument.Id + `?lastModified=${selectedMinutes.HtmlDocument.LastModified}`, 'aria-label': localization.downloadMinutesLinkLabel }).text(localization.minutesLabel + ' ' + localization.packageLabel);
				$(document.getElementById(documentPrintVersionClientId)).removeClass('hidden');
			}
			else {
				$(document.getElementById(documentPrintVersionClientId)).addClass('hidden');
			}
		}

		if ($(document.getElementById(documentPrintVersionClientId)).is(':visible') || $(document.getElementById(documentCoverPdfClientId)).is(':visible')) {
			$('#print-version-label').show();
		}

		if (includeMinutesAttachments === false) {
			$(document.getElementById(documentCoverPdfClientId)).hide();
			$(document.getElementById(documentPrintVersionClientId)).text(localization.minutesLabel).css({ 'margin-left': '0' });
		}
	};

	var changeUrl = function (d) {
		var currentPage = window.location.href;
		var pageUrl;
		if (currentPage.toLowerCase().indexOf('&id=') > 0) {
			pageUrl = currentPage.substr(0, currentPage.toLowerCase().indexOf('&id='));
			history.pushState('Meeting Id' + d, document.title, pageUrl + '&Id=' + d + (contentOnly ? '&content=true' : ''));
		}
		else if (currentPage.toLowerCase().indexOf('?id=') > 0) {
			pageUrl = currentPage.substr(0, currentPage.toLowerCase().indexOf('?id='));
			history.pushState('Meeting Id' + d, document.title, pageUrl + '?Id=' + d + (contentOnly ? '&content=true' : ''));
		}
	};

	//#region Map Functions
	var loadLocationItems = function (meetingId) {
		if (meetingId > 0) {
			map = null;
			$(document.getElementById('map')).hide();
			$(document.getElementById(agendaShowMapButtonClientId)).hide();
			$(document.getElementById(agendaHideMapButtonClientId)).hide();
			$(document.getElementById('MeetingDocumentContainer')).show();

			$.ajax({
				url: '/Services/MeetingsService.svc/meetings/' + meetingId + '/locationItems',
				contentType: 'application/json', dataType: 'json', async: true, type: 'GET', cache: false, timeout: 30000,
				success: function (result) {
					if (result && result.length > 0) {
						locationItems = [];
						for (var i = 0; i < result.length; i++) {
							var item = result[i];
							var locationItem = {
								id: item.Id,
								description: item.Description,
								bullet: item.Bullet,
								latitude: item.Latitude,
								longitude: item.Longitude,
								locationAddress: item.LocationAddress,
								attachments: item.Attachments
							};
							locationItems.push(locationItem);
						}
						$(document.getElementById(agendaShowMapButtonClientId)).show();
						$(document.getElementById(agendaShowMapButtonClientId)).off('click').on('click', showAgendaMapClick);
						$(document.getElementById(agendaHideMapButtonClientId)).off('click').on('click', hideAgendaMapClick);
					}
				}
			});
		}
	};

	var addMarkersToLocationItems = function (items) {
		$(document.getElementById(meetingDocumentClientId)).contents().find('img[id^=agenda-item-location-]').remove();
		for (var i = 0; i < items.length; i++) {
			var item = items[i];
			var agendaItem = $(document.getElementById(meetingDocumentClientId)).contents().find('a[name="' + documentAgendaItemClientId + item.id + '"]');
			if (agendaItem.length > 0) {
				var markerImage = $('<img />').attr({ 'id': 'agenda-item-location-' + item.id, 'item-id': item.id, 'src': 'https://i.civicweb.net/Global/Images/marker.png' }).css({ 'cursor': 'pointer', 'vertical-align': 'text-bottom' }).on('click', openMapAtItem);
				agendaItem.after(markerImage);
			}
		}
	};

	var openMapAtItem = function (e) {
		showAgendaMapClick(e);

		if (map) {
			var id = parseInt($(e.target).attr('item-id'));
			var marker = getMarkerById(id);
			// ReSharper disable once ConstructorCallNotUsed
			// ReSharper disable once InconsistentNaming
			new window.google.maps.event.trigger(marker, 'click');
		}

		e.preventDefault();
	};

	var showAgendaMapClick = function (e) {
		if (window.google && window.google.maps) {
			if (!map && locationItems) {
				var settings = {
					zoom: parseFloat(defaultZoom) > 0 ? parseFloat(defaultZoom) : parseFloat(15),
					center: new window.google.maps.LatLng(defaultLatitude, defaultLongitude),
					mapTypeControl: true,
					mapTypeControlOptions: { style: window.google.maps.MapTypeControlStyle.DROPDOWN_MENU },
					navigationControl: true,
					navigationControlOptions: { style: window.google.maps.NavigationControlStyle.SMALL },
					mapTypeId: window.google.maps.MapTypeId.ROADMAP
				};
				$(document.getElementById('MeetingDocumentContainer')).hide();
				$(document.getElementById('map')).show();
				var containerWidth = $(document.getElementById('meeting-documents')).width();
				$(document.getElementById('map')).css({ 'width': containerWidth, 'height': '40em' });
				map = new window.google.maps.Map(document.getElementById('map'), settings);
				var infoWindow = new window.google.maps.InfoWindow();
				markers = [];
				for (var i = 0; i < locationItems.length; i++) {
					var item = locationItems[i];
					var marker = new window.google.maps.Marker({
						position: new window.google.maps.LatLng(item.latitude, item.longitude),
						id: item.id,
						map: map
					});
					markers.push(marker);
					addMarkerClickEvent(map, infoWindow, item, marker);
				}
			}
			else {
				$(document.getElementById('MeetingDocumentContainer')).hide();
				$(document.getElementById('map')).show();
			}
			$(document.getElementById(agendaShowMapButtonClientId)).hide();
			$(document.getElementById(agendaHideMapButtonClientId)).show();
		}

		e.preventDefault();
	};

	var hideAgendaMapClick = function (e) {
		$(document.getElementById('map')).hide();
		$(document.getElementById('MeetingDocumentContainer')).show();
		$(document.getElementById(agendaShowMapButtonClientId)).show();
		$(document.getElementById(agendaHideMapButtonClientId)).hide();

		e.preventDefault();
	};

	var addMarkerClickEvent = function (map, infoWindow, item, marker) {
		window.google.maps.event.addListener(marker, 'click', function () {
			var address = '<div style="font-weight: bold;">' + localization.agendaItemLocationLabel + ':</div><div>' + item.locationAddress + '</div><br/>';
			var bullet = '<div><span style="font-weight: bold; margin-right:10px;">' + item.bullet + '</span>';
			var description = '<span>' + item.description + '</span></div><br/>';
			var attachmentList = '';
			if (item.attachments.length > 0) {
				attachmentList = '<div style="font-weight: bold; width: 100%; clear:both;">' + localization.attachmentsLabel + '</div>';
				for (var i = 0; i < item.attachments.length; i++) {
					var attachment = item.attachments[i];
					attachmentList += '<a href="/document/' + attachment.DocumentID + '">' + attachment.Name + '</a><br />';
				}
			}

			infoWindow.setContent('<div class=\'marker-popup\'>' + address + bullet + description + attachmentList + '</div>');
			infoWindow.open(map, marker);
		});
	};

	var getMarkerById = function (id) {
		var found = null;
		if (markers) {
			for (var i = 0; i < markers.length; i++) {
				var marker = markers[i];
				if (marker.id === id) {
					found = marker;
				}
			}
		}
		return found;
	};
	//#endregion

	var resizeDocumentFrame = function (iframe) {
		var frame = $(iframe);
		var siteToReach = frame.attr('src');
		try {
			frame.height(frame.contents().find('body').prop('offsetHeight'));
		}
		catch (ex) {
			if (ex.message.toLocaleLowerCase().indexOf('permission denied') !== -1) {
				frame.attr('src', '');
				setTimeout(function () {
					frame.height('15em');
					frame.contents().find('body').empty();
					frame.contents().find('body').append($('<div></div>').css({ 'font-size': '1.5em', 'text-align': 'center' }).text(localization.warningMessageErrorLoadingIframeContent)
						.prepend($('<img />').attr({ 'src': '/Global/Images/PortalIcons/warning.png', 'title': localization.warningMessageErrorLoadingPage }).css({ 'vertical-align': 'middle', 'margin': '0 0.3em' })))
						.append($('<a></a>').attr({ 'href': siteToReach }).css({ 'display': 'block', 'text-align': 'center' }).text(localization.openInNewWindowLabel));
				}, 0);
			}
		}

		if (locationItems && locationItems.length > 0) {
			addMarkersToLocationItems(locationItems);
		}
	};

	(function () {
		if (purchasedVideo) {
			CivicWeb.Integration.Video.createInstance(args);
		}
		if (CivicWeb.Portal && CivicWeb.Portal.EditItemControl) {
			$(document.getElementById(editButtonClientId)).off('click').on('click', CivicWeb.Portal.EditItemControl.openItem);
		}
		$(document.getElementById(nextButtonClientId)).off('click').on('click', nextButtonClick).on('keypress', function (e) { if (e.keyCode == 13) nextButtonClick() });
		$(document.getElementById(prevButtonClientId)).off('click').on('click', prevButtonClick).on('keypress', function (e) { if (e.keyCode == 13) prevButtonClick() });

		//disable hitting the enter key and the whole page reloads
		$('#edit-external-links-popup input').keypress(function (e) {
			if (e.keyCode === '13') {
				e.preventDefault();
				return false;
			}
			return true;
		});

		$(document.getElementById(videoButtonClientId)).on('click', videoButtonClick);

		if (document.getElementById('minutes-document-link-selector')) {
			$(document.getElementById(editExternalLinksClientId)).off('click').on('click', editExternalLinksClick);
			$(document.getElementById('close-edit-external-links-popup')).off('click').on('click', function () { $(document.getElementById('edit-external-links-popup')).hide(); $(document.getElementById('MeetingDocumentContainer')).show(); });
			$(document.getElementById('close-external-links')).off('click').on('click', function () { $(document.getElementById('edit-external-links-popup')).hide(); $(document.getElementById('MeetingDocumentContainer')).show(); });
			$(document.getElementById('edit-external-links-popup')).draggable();
			$(document.getElementById('external-minutes-link-url')).off('blur').on('blur', minutesLinkUrlBlur);
			$(document.getElementById('external-link-url')).off('blur').on('blur', externalLinkUrlBlur);
			$(document.getElementById('save-external-links')).off('click').on('click', saveExternalLinksClick);
			$(document.getElementById('delete-external-link')).off('click').on('click', deleteExternalLinkClick);
			$(document.getElementById('delete-external-minutes-link')).off('click').on('click', deleteExternalLinkClick);
			$(document.getElementById(uploadMinutesClientId)).off('click').on('click', uploadMinutesClick);
			$(document.getElementById('upload-minutes-select')).off('change').on('change', uploadMinutesSelectChange);
			$(document.getElementById('remove-minutes')).off('click').on('click', removeMinutesClick);

			CivicWeb.Common.Notification.create('replace-minutes-button-warning', CivicWeb.Common.Notification.types.warning, localization.warningMessagePortalEditReplaceMinutesButton, false);
			CivicWeb.Common.Notification.create('minutes-notification', CivicWeb.Common.Notification.types.success, localization.notificationSuccess, true);
		}

		$('button.apply-button').off('click').on('click', applyButtonClick);
		$(document.getElementById('board-application-trackers')).off('change').on('change', boardApplicationTrackerSelectChange);

		setTimeout(function () { $('.meeting-list-item-button-selected').click(); }, 50);
		setTimeout(function () {
			var selectedGroup = $('.meeting-list-item-group-selected');
			var meetingGroups = $('.meeting-list-item-group');
			if (!selectedGroup.length && meetingGroups.length) {
				$(meetingGroups[0]).removeClass('meeting-list-item-group').addClass('meeting-list-item-group-selected');
			}
		}, 50);
		$(document).ready(function () {
			$(document.getElementById(meetingDocumentClientId)).on('load', function () {
				//Do this after the document iframe loads content
				hideDocumentLoading();

				$.each($(this).contents().find('table'), function (index, node) {
					if ($(node).attr('style') && $(node).attr('style').indexOf('width') > -1) {
						var width = $(node).css('width');
						$(node).css({ 'max-width': width });
					}
				});

				resizeDocumentFrame(this);
			});

			setTimeout(function () { $('html,body').animate({ scrollTop: $(document.getElementById('newMeetingList')).offset().top - 10 }); }, 250);
		});

		$('[data-toggle="tooltip"]').tooltip();
	})();
};

//Objects
Portal.MeetingInformationPage = {
	//Properties
	instance: null,

	//Methods
	createInstance: function (args) {
		if (this.instance) {
			delete this.instance;
		}
		this.instance = new Portal.MeetingInformation(args);
	},

	events: {
		meetingClick: function (e, packageId, typeId, outputTypeId) {
			Portal.MeetingInformationPage.instance.meetingClick(e, packageId, typeId, outputTypeId);
		},
		meetingDocumentTypeClick: function (type) {
			Portal.MeetingInformationPage.instance.meetingDocumentTypeClick(type);
		},
		addExternalLink: function (meetingId) {
			Portal.MeetingInformationPage.instance.addExternalLink(meetingId);
		},
		OnClientCloseRadTrackerWindow: function () {
			Portal.MeetingInformationPage.instance.PortalCloseRadTrackerWindow();
		}
	}
};
;
// Declare namespaces
var CivicWeb = CivicWeb || {};
CivicWeb.Integration = CivicWeb.Integration || {};

//Create classes
CivicWeb.Integration.VideoClass = function (args) {
	var localization = args.localization;
	var referenceFieldLocalization = args.referenceFieldLocalization;

	var minutesBuild = args != null && args.minutesBuild != null ? args.minutesBuild : false;
	var agendaDocument = args != null && args.agendaDocument != null ? args.agendaDocument : false;
	var meetingId = args != null && args.meetingId != null ? args.meetingId : 0;
	var createEvent = args != null && localization.createEvent != null ? localization.createEvent : '';
	var viewEvent = args != null && localization.viewEvent != null ? localization.viewEvent : '';
	var audioOnly = args != null && args.audioOnly != null ? args.audioOnly : false;
	var earthChannel = args != null && args.earthChannel != null ? args.earthChannel : false;
	var youTubeLite = args != null && args.youTubeLite != null ? args.youTubeLite : false;
	var youTube = args != null && args.youTube != null ? args.youTube : false;
	var youTubeEventId = args != null && args.youTubeEventId != null ? args.youTubeEventId : '';
	var manageVideo = args != null && args.manageVideo != null ? args.manageVideo : false;
	var purchasedBoxcast = args != null && args.purchasedBoxcast != null ? args.purchasedBoxcast : false;
	var timestampEnabled = args != null && args.timestampEnabled != null ? args.timestampEnabled : false;
	var documentBody = null;
	var myVideoWindow = null;
	var setVideoTimeStampDataCallback = function (seconds) { };
	var itemId = 0;

	var isPhone = false;
	var isIOS = false;
	var liveTimestamping = false;
	var liveTimestampingFirstTimestamp = null;
	var syncModeEnabled = false;
	var historic = false;
	var firstTimeStamp = Number.MAX_SAFE_INTEGER;
	var startAtFirstTimestamp = false;

	var attachmentPane = null;
	var videoHeight = 300;
	var videoWidth = 400;
	var videoScale = 0.618;
	var maxVideoWidth = 505;
	var ratio4x3 = 0.75;
	var ratio16x9 = 0.5625;
	var minWidthChromeLoad4x3 = 400;
	var minWidthChromeLoad16x9 = 464;
	var earthChannelForcedMinHeight = 200;//we are waiting for them to remove this limit

	//these variables are for multi event meetings
	var currentVideo = 0;
	var videoRatio = [];
	var urlBase = [];
	var videoObjects = [];
	var videoElement = [];
	var youTubeEvents = [];
	var liveEventExists = false;
	var searchingForAdditionalEvents = null;
	var queryValues;
	var eventIds = [];
	var broadcastsChannels = {};
	var nextPageToken = "";

	const youtubeText = "YouTube - ";
	const boxcastText = "Boxcast - "

	this.addVideoButtonToPortal = function (meetingId, documentId, buttonClient) {
		$.ajax({
			url: '/api/videolink/' + meetingId.toString(),
			contentType: 'application/json', dataType: 'json', async: true, cache: false, type: 'GET',
			success: function (data) {
				var linkFound = false;
				if (data && data.length > 0) {
					if (!youTube && data.indexOf('IsMediaEnabled') < 0) {
						//Granicus
						if (buttonClient.is('a')) {
							buttonClient.show().removeClass('hidden').text(localization.audioVideoLabel);
						}
						else {
							buttonClient.show().removeClass('hidden').find('span').text(localization.audioVideoLabel);
						}
						buttonClient.attr({ 'href': data });
						linkFound = true;
					}
					else {
						var result = JSON.parse(data);
						currentVideo = 0;
						urlBase = [];
						for (var i = 0; i < result.length; i++) {
							var d = result[i];

							var isMediaEnabled = d.IsMediaEnabled ? d.IsMediaEnabled : false;
							var publisherEventId = d.PublisherEventID ? d.PublisherEventID : 0;
							var eventStatus = d.EventStatus ? d.EventStatus : '';
							var youTubeEventId = d.YouTubeEventId ? d.YouTubeEventId : '';
							var showVideoLink = d.ShowVideoLink ? d.ShowVideoLink : false;
							historic = d.Historic ? d.Historic || historic : false;

							if ((youTube && showVideoLink && youTubeEventId.length > 0 && youTubeEventId != '0') || eventStatus.toLowerCase() == 'published' && isMediaEnabled && publisherEventId > 0) {
								if (buttonClient.is('a')) {
									buttonClient.show().removeClass('hidden').text(localization.audioVideoLabel);
								}
								else {
									buttonClient.show().removeClass('hidden').find('span').text(localization.audioVideoLabel);
								}

								if (historic) {
									var currentUrlBase = d.URLBase.replace('view.', 'viewer.') + '&eID=' + publisherEventId;
									urlBase.push(currentUrlBase);
									buttonClient.off('click', showVideo).on('click', showVideo);
								}
								else {
									buttonClient.off('click', showVideo);
									buttonClient.attr({ 'href': '/document/' + documentId + '?splitscreen=true&media=true' });
								}
								linkFound = true;
								break;
							}
						}
					}
				}

				if (!linkFound) {
					buttonClient.hide().addClass('hidden');
				}
			},
			error: function () {
				buttonClient.hide().addClass('hidden');
			}
		});

	};

	this.showPdfQuickViewVideoLink = function (meetingId, documentId) {
		$.ajax({
			url: '/api/videolink/' + meetingId.toString(),
			contentType: 'application/json', dataType: 'json', async: true, cache: false, type: 'GET',
			success: function (data) {
				var linkFound = false;
				if (data && data.length > 0) {
					if (!youTube && data.indexOf('IsMediaEnabled') < 0) {
						//Granicus
						$('#VideoLink > a > span').text(localization.audioVideoLabel).attr('title', localization.showAudioVideoLabel);
						$('#VideoLink > a').attr({ 'href': data });
						linkFound = true;
					}
					else {
						var result = JSON.parse(data);
						currentVideo = 0;
						urlBase = [];
						for (var i = 0; i < result.length; i++) {
							var d = result[i];

							var isMediaEnabled = d.IsMediaEnabled ? d.IsMediaEnabled : false;
							var publisherEventId = d.PublisherEventID ? d.PublisherEventID : 0;
							var eventStatus = d.EventStatus ? d.EventStatus : '';
							var youTubeEventId = d.YouTubeEventId ? d.YouTubeEventId : '';
							var showVideoLink = d.ShowVideoLink ? d.ShowVideoLink : false;
							historic = d.Historic ? d.Historic || historic : false;

							if ((youTube && showVideoLink && youTubeEventId.length > 0 && youTubeEventId != '0') || eventStatus.toLowerCase() == 'published' && isMediaEnabled && publisherEventId > 0) {
								$('#VideoLink > a').attr({ 'href': '/document/' + documentId + '?splitscreen=true&media=true' });
								linkFound = true;
								break;
							}
						}
					}

					if (linkFound) {
						$('#VideoLink').removeClass('hidden');
					}
				}
			},
			error: function () {
				buttonClient.hide();
			}
		});
	};

	this.addTimestampsAndVideoToMeetingDocument = function (id, body, splitscreen) {

		if (window.location.href.indexOf('eventwithindexpoints') > 0 && (queryValues.eventwithindexpoints == "false" || queryValues.eventwithindexpoints == "0"))
		{
			return false;
		}
		$.ajax({
			url: '/api/geteventwithindexpoints/' + id.toString(),
			contentType: 'application/json', dataType: 'json', async: true, cache: false, type: 'GET',
			success: function (result) {
				if (result) {
					if (result.length > 0) {
						youTube = result[0].YouTube != null ? result[0].YouTube : false;
					}

					if (result && result.length > 0) {
						//Do these once on load, not per event
						body.find('a[id^=video-timestamp-]').remove();

						currentVideo = 0;
						videoRatio = [];
						urlBase = [];
						videoElement = [];
						youTubeEvents = [];
						var videoExists = false;
						var showVideoLink = true;
						var showTimeStamps = false;
						var liveTimestamping = false;

						var agendaIds = [];
						var minutesIds = [];
						var iconLight = audioOnly ? '/Global/Images/icon-audio-light-16x16.png' : '/Global/Images/icon-video-light-16x16.png';
						var iconDark = audioOnly ? '/Global/Images/icon-audio-dark-16x16.png' : '/Global/Images/icon-video-dark-16x16.png';

						documentBody = body;

						eventIds = [];
						for (var k = 0; k < result.length; k++) {
							var dat = result[k];
							var event = dat.Event != null ? dat.Event : null;
							var eventId = event != null && event.eventId != null ? event.eventId : '';
							if (eventIds.indexOf(eventId) == -1) {
								eventIds.push(eventId);
							}
						}

						for (var i = 0; i < result.length; i++) {
							var d = result[i];
							var isMediaEnabled = d.PublisherEvent ? d.PublisherEvent.IsMediaEnabled : false;
							var publisherEventId = d.PublisherEvent ? d.PublisherEvent.PublisherEventID : 0;
							var eventStatus = d.PublisherEvent ? d.PublisherEvent.EventStatus : '';

							var event = d.Event != null ? d.Event : null;
							var eventId = event != null && event.eventId != null ? event.eventId : '';
							//var eventTitle = event != null && event.eventTitle != null ? event.eventTitle : '';

							if (event && event.broadcastChannel && event.channelId)
							{
								event.eventId = event.channelId;
								eventId = event.channelId;
							}
							if (i == 0) {
								historic = d.Historic != null ? d.Historic : false;

								showVideoLink = d.ShowVideoLink != null ? d.ShowVideoLink : true;
								showTimeStamps = d.ShowTimeStamps != null ? d.ShowTimeStamps : false;
								startAtFirstTimestamp = d.StartAtFirstTimestamp != null ? d.StartAtFirstTimestamp : false;
								liveTimestamping = d.PublisherEvent != null ? d.PublisherEvent.MediaType.toLowerCase() == 'live' : false;
							}

							if ((youTube && showVideoLink && eventId.length > 0 && eventId != '0') || (eventStatus.toLowerCase() == 'published' && isMediaEnabled && publisherEventId > 0)) {
								if (showTimeStamps) {
									var localIndexPoints = result[i].LocalIndexPoints ? result[i].LocalIndexPoints : null;
									if (localIndexPoints) {
										for (var j = 0; j < localIndexPoints.length; j++) {
											var minutesItemId = localIndexPoints[j].ItemId;
											var secondsStart = localIndexPoints[j].Value;
											var timeStampEvent = localIndexPoints[j].Event != null ? localIndexPoints[j].Event : '';
											var relationshipTypeId = localIndexPoints[j].RelationshipTypeId;
											var agendaRelatedItemId = localIndexPoints[j].RelatedItem;

											if (!isNaN(secondsStart) && (timeStampEvent == eventId || timeStampEvent == '')) {
												var timeString = convertSecondsToTimeString(secondsStart, false, minutesItemId, timeStampEvent);
												var timestampLink = $('<a />').attr({ 'title': timeString, 'time-stamp-event': eventId, 'time-stamp-video': i, 'time-stamp': secondsStart }).css({ 'position': 'absolute', 'right': '0', 'cursor': 'pointer', 'text-decoration': 'underline', 'z-index': '500' }).on('click', function () { gotoVideoTimeStamp(this); }).append($('<img />').css({ 'width': '20px', 'height': '20px' }).attr({ 'src': iconLight }).hover(function () { $(this).attr('src', iconDark); }, function () { $(this).attr('src', iconLight); }));

												if (minutesIds.indexOf(parseInt(minutesItemId)) < 0) {
													var minutesHeading = body.find('a[name=MinutesHeading' + minutesItemId + ']');
													if (minutesHeading.length > 0) {
														timestampLink.attr({ 'id': 'video-timestamp-' + minutesItemId, 'top': minutesHeading.top });
														minutesHeading.parent().after(timestampLink);
													}
													var minutesItem = body.find('a[name=MinutesItem' + minutesItemId + ']');
													if (minutesItem.length > 0) {
														timestampLink.attr({ 'id': 'video-timestamp-' + minutesItemId, 'top': minutesItem.top });
														minutesItem.parent().after(timestampLink);
													}
													var resolutionItem = body.find('a[name=Resolution' + minutesItemId + ']');
													if (resolutionItem.length > 0) {
														timestampLink.attr({ 'id': 'video-timestamp-' + minutesItemId, 'top': resolutionItem.top });
														resolutionItem.parent().after(timestampLink);
													}

													minutesIds.push(minutesItemId)
												}

												var agendaItemId = agendaRelatedItemId || (minutesItemId - 1);
												if ((relationshipTypeId == 6 || secondsStart > 0) && agendaIds.indexOf(parseInt(agendaItemId)) < 0) {
													var agendaHeading = body.find('a[name=AgendaHeading' + agendaItemId + ']');
													if (agendaHeading.length > 0) {
														timestampLink.attr({ 'id': 'video-timestamp-' + agendaItemId, 'top': agendaHeading.top });
														agendaHeading.parent().after(timestampLink);
													}
													var agendaItem = body.find('a[name=AgendaItem' + agendaItemId + ']');
													if (agendaItem.length > 0) {
														timestampLink.attr({ 'id': 'video-timestamp-' + agendaItemId, 'top': agendaItem.top });
														agendaItem.parent().after(timestampLink);
													}
													var agendaWrapper = body.find('.word-margins').first();
													agendaWrapper.css('position', 'relative');

													var recommendation = body.find('a[name=Recommendation' + agendaItemId + ']');

													if (recommendation.length > 0) {

														timestampLink.attr('id', 'video-timestamp-' + agendaItemId);

														var top =
															recommendation.offset().top - agendaWrapper.offset().top;
														var rightPadding = parseFloat(agendaWrapper.css('padding-right')) || 0;
														timestampLink.css({
															position: 'absolute',
															right: (-rightPadding) + 'px',
															top: top + 'px',
															zIndex: 500
														});

														agendaWrapper.append(timestampLink);
													}

													agendaIds.push(agendaItemId);
												}

												if (firstTimeStamp > secondsStart) {
													firstTimeStamp = secondsStart;
												}
											}
										}
									}

									if (!liveTimestamping && d.IndexPoints != null) {
										for (var k = 0; k < d.IndexPoints.length; k++) {
											var externalId = d.IndexPoints[k].ExternalID;
											var secondsStart = d.IndexPoints[k].SecondsStart;
											var validTimestamp = !isNaN(secondsStart) && parseInt(secondsStart) > 0 || !isNaN(d.IndexPoints[k].SecondsEnd) && parseInt(d.IndexPoints[k].SecondsEnd) > 0;
											var title = d.IndexPoints[k].Title;
											if (validTimestamp && agendaIds.indexOf(parseInt(externalId)) < 0) {
												var timeString = convertSecondsToTimeString(secondsStart);
												var timestampLink = $('<a />').attr({ 'title': timeString, 'time-stamp-video': i, 'time-stamp': secondsStart }).css({ 'position': 'absolute', 'right': '0', 'cursor': 'pointer', 'text-decoration': 'underline', 'z-index': '500' }).on('click', function () { gotoVideoTimeStamp(this); }).append($('<img />').css({ 'width': '20px', 'height': '20px' }).attr({ 'src': iconLight }).hover(function () { $(this).attr('src', iconDark); }, function () { $(this).attr('src', iconLight); }));

												var agendaHeading = body.find('a[name=AgendaHeading' + externalId + ']');
												if (agendaHeading.length > 0) {
													timestampLink.attr({ 'id': 'video-timestamp-' + externalId, 'top': agendaHeading.top });
													agendaHeading.parent().after(timestampLink);
												}
												var agendaItem = body.find('a[name=AgendaItem' + externalId + ']');
												if (agendaItem.length > 0) {
													timestampLink.attr({ 'id': 'video-timestamp-' + externalId, 'top': agendaItem.top });
													agendaItem.parent().after(timestampLink);
												}
												var agendaWrapper = body.find('.word-margins').first();
												agendaWrapper.css('position', 'relative');

												var recommendation = body.find('a[name=Recommendation' + agendaItemId + ']');

												if (recommendation.length > 0) {

													timestampLink.attr('id', 'video-timestamp-' + agendaItemId);

													var top =
														recommendation.offset().top - agendaWrapper.offset().top;
													var rightPadding = parseFloat(agendaWrapper.css('padding-right')) || 0;
													timestampLink.css({
														position: 'absolute',
														right: (-rightPadding) + 'px',
														top: top + 'px',
														zIndex: 500
													});

													agendaWrapper.append(timestampLink);
												}

												agendaIds.push(externalId);
											}

											if (firstTimeStamp > secondsStart) {
												firstTimeStamp = secondsStart;
											}
										}
									}

								}

								var currentVideoRatio = (d.PublisherEvent && (parseInt(d.PublisherEvent.EnabledItemMask) & 4096) > 0) ? ratio16x9 : ratio4x3;
								videoRatio.push(currentVideoRatio);
								youTubeEvents.push(event);

								setVideoWidthHeight(currentVideoRatio);

								if (youTube && eventId.length > 0) {
									videoElement.push('<div id="videoDiv" height="' + videoHeight + 'px" width="' + videoWidth + 'px" style=" margin-top:' + (splitscreen ? '0em;' : '2.5em;') + ' text-align: center; top: 0; width:100%; background-color: white; z-index: 600; "><div id="timeStampVideoDiv"></div><hr style="margin:0"/></div>');
								}
								else if (historic) {
									var currentUrlBase = d.PublisherEvent.URLBase.replace('view.', 'viewer.') + '&eID=' + publisherEventId;
									urlBase.push(currentUrlBase);
								}
								else {
									var currentUrlBase = (d.PublisherEvent ? d.PublisherEvent.URLBase.replace('http://view.earthchannel.com/PlayerController.aspx', '//viewer.earthchannel.com/PlayerMedia.aspx') : '') + '&amp;eID=' + publisherEventId + '&amp;mode=embed';
									urlBase.push(currentUrlBase);
									videoElement.push('<div id="videoDiv" style=" margin-top:' + (splitscreen ? '0em;' : '2.5em;') + ' text-align: center;"><iframe id="iframeONE" height="' + videoHeight + 'px" width="' + videoWidth + 'px" src="' + currentUrlBase + '" scrolling="no" frameborder="0" marginheight="0" marginwidth="0"></iframe><hr style="margin:0"/></div>');
								}
								videoExists = true;
							}
						}

						youTubeEventId = youTubeEvents.length > 0 && youTubeEvents[0] != null && youTubeEvents[0].eventId != null ? youTubeEvents[0].eventId : '';

						if (youTube && youTubeEventId != '') {
							attachmentPane = $('#attachment-pane');
							if (attachmentPane.length == 0 && window.parent.$) {
								attachmentPane = window.parent.$('#attachment-pane');
							}

							if (attachmentPane.length > 0) {
								videoScale = 1;
								maxVideoWidth = 800;

								body.find('a[target="AgendaAttachment"]').on('click', function () { if (attachmentPane && (attachmentPane).find('#videoDiv').length > 0) { setTimeout(function () { moveVideoToAgendaFrame(true); }, 0); } });
							}
							else {
								attachmentPane = null;
							}
						}

						if (videoExists && showVideoLink) {
							//----------------------------------------------------
							//common to multi events
							(attachmentPane ? attachmentPane : documentBody).css({ 'margin': '0' });
							(attachmentPane ? attachmentPane : documentBody).css({ 'padding': '0' });

							$(window).on('resize', setVideoSize);

							$('#video-button').removeClass("hidden").find('span[class="toolbar-text"]').text(localization.audioVideoLabel);
							var closeSpltiscreenButton = $('ul.split-screen-toolbar').find('li#close-split-screen');
							if (closeSpltiscreenButton && closeSpltiscreenButton.length > 0 && typeof window.CivicWeb != 'undefined' && typeof window.CivicWeb.Documents != 'undefined' && typeof window.CivicWeb.Documents.SplitscreenPage != 'undefined') {
								window.CivicWeb.Documents.SplitscreenPage.setToolbarCollapsedState();
							}

							$('#video-button').off('click keypress').on('click', showVideo).on('keypress', function (event) {
								if (event.which == 13 || event.which == 32) {
									showVideo(event);
									return;
								}
							}).attr({ 'title': localization.showAudioVideoLabel, 'aria-label': localization.showAudioVideoLabel });

							//auto play from meeeting list widget and portal video button
							if (window.location.href.indexOf('media=true') > 0 || window.location.href.indexOf('timestamp') > 0) {
								if (isPhone && splitscreen && ($(window).height() > $(window).width())) {
									//moveVideoToAgendaFrame(false);
								}
								else {
									if (window.location.href.indexOf('timestamp') > 0) {
										startAt = queryValues.timestamp;
									}
									showVideo();
								}
							}
						}
					}
					else {

					}
				}
			},
			error: function () {
				//return '';
			}
		});
	};

	var setVideoWidthHeight = function (currentVideoRatio) {
		var bodyWidth = (attachmentPane ? attachmentPane : documentBody).width();
		videoWidth = (!isNaN(bodyWidth) ? parseFloat(bodyWidth) : minWidthChromeLoad4x3) * videoScale;

		if (videoWidth > maxVideoWidth) {
			videoWidth = maxVideoWidth;
		}

		if (videoWidth < minWidthChromeLoad4x3 && navigator.userAgent.indexOf('Chrome') != -1 && currentVideoRatio == ratio4x3 && !youTube) {
			//4:3
			videoWidth = minWidthChromeLoad4x3;
			(attachmentPane ? attachmentPane : documentBody).attr('width', minWidthChromeLoad4x3);
		}
		else if (videoWidth < minWidthChromeLoad16x9 && navigator.userAgent.indexOf('Chrome') != -1 && currentVideoRatio == ratio16x9 && !youTube) {
			//16:9
			videoWidth = minWidthChromeLoad16x9;
			(attachmentPane ? attachmentPane : documentBody).attr('width', minWidthChromeLoad16x9);
		}

		videoHeight = videoWidth * currentVideoRatio;
	};

	var switchEvents = function (currentEventId) {
		if (youTubeEvents != null) {
			for (var i = 0; i < youTubeEvents.length; i++) {
				if (youTubeEvents[i].eventId != null && youTubeEvents[i].eventId == currentEventId) {
					currentVideo = i;
					youTubeEventId = youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo].eventId != null ? youTubeEvents[currentVideo].eventId : '';
					window.myPlayer.loadVideoById(youTubeEventId, 0, "large");

					break;
				}
			}
		}
	};

	this.getEvents = function () {
		return youTubeEvents;
	};

	this.getCurrentEvent = function () {
		return youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo] != null ? youTubeEvents[currentVideo] : null;
	};

	this.getVideoTime = function (iframe, id, callback) {
		if (liveTimestamping) {
			if (liveTimestampingFirstTimestamp == null) {
				liveTimestampingFirstTimestamp = new Date();
				callback(id, 0, true, youTubeEventId);
			}
			else {
				var liveTimestampingTimestamp = new Date();
				var difference = Math.round((liveTimestampingTimestamp - liveTimestampingFirstTimestamp) / 1000);
				callback(id, difference, true, youTubeEventId);
			}
		}
		else {
			if (youTube && window.myPlayer != null) {
				callback(id, Math.round(window.myPlayer.getCurrentTime()), true, youTubeEventId);
			}
			else {
				itemId = id;
				setVideoTimeStampDataCallback = callback;
				if (iframe) {
					var a = $('<a>', { href: iframe.src })[0];
					var url = a.origin ? a.origin : (a.protocol + "//" + a.host.replace(":80", "").replace(":443", ""));
					var ifr = iframe.contentWindow ? iframe.contentWindow : iframe.contentDocument.defaultView;
					ifr.postMessage("GETTIME", url);
				}
			}
		}

	};

	var gotoVideoTimeStamp = function (e) {
		var timeStampVideo = !isNaN($(e).attr('time-stamp-video')) ? parseInt($(e).attr('time-stamp-video')) : 0;
		var secs = !isNaN($(e).attr('time-stamp')) ? parseInt($(e).attr('time-stamp')) : 0;

		secs = secs < 0 ? '0' : secs.toString();

		if (isIOS) {
			showVideo();
			var iframe = (attachmentPane ? attachmentPane : documentBody).find('#timeStampVideoDiv')[0];
			if (iframe) {
				var uri = iframe.src;
				var re = new RegExp('([?|&])start=.*?(&|$)', 'i');
				var newUri;
				var separator = uri.indexOf('?') !== -1 ? '&' : '?';
				if (uri.match(re)) {
					newUri = uri.replace(re, separator + 'start=' + secs + '$2');
				}
				else {
					newUri = uri + separator + 'start=' + secs;
				}
				iframe.src = newUri;
			}
		}
		else {
			if (youTube && youTubeEvents[currentVideo] != null && youTubeEvents[timeStampVideo] != null) {
				if (window.myPlayer != null) {
					if (timeStampVideo != currentVideo) {
						currentVideo = timeStampVideo;
						youTubeEventId = youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo].eventId != null ? youTubeEvents[currentVideo].eventId : '';

						window.myPlayer.loadVideoById(youTubeEventId, secs, "large");
					}
					else {
						window.myPlayer.seekTo(secs);
					}
				}
				else {
					hideVideo();
					currentVideo = timeStampVideo;
					youTubeEventId = youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo].eventId != null ? youTubeEvents[currentVideo].eventId : '';
					startAtFirstTimestamp = true;
					firstTimeStamp = secs;
					showVideo();
				}
			}
			else if (timeStampVideo != currentVideo) {
				hideVideo();
				currentVideo = timeStampVideo;
				showVideo();
				var iframe = (attachmentPane ? attachmentPane : documentBody).find('#iframeONE')[0];
				$(iframe).on('load', function () {
					setTimeout(function () {
						var a = $('<a>', { href: iframe.src })[0];
						var url = a.origin ? a.origin : (a.protocol + "//" + a.host.replace(":80", "").replace(":443", ""));
						var ifr = iframe.contentWindow ? iframe.contentWindow : iframe.contentDocument.defaultView;
						ifr.postMessage("SETTIME:" + secs, url);
					}, 100);
				});
			}
			else {
				var iframe = (attachmentPane ? attachmentPane : documentBody).find('#iframeONE')[0];
				if (iframe) {
					var a = $('<a>', { href: iframe.src })[0];
					var url = a.origin ? a.origin : (a.protocol + "//" + a.host.replace(":80", "").replace(":443", ""));
					var ifr = iframe.contentWindow ? iframe.contentWindow : iframe.contentDocument.defaultView;
					ifr.postMessage("SETTIME:" + secs, url);
				}
				else {
					hideVideo();
					showVideo();
					var iframe = (attachmentPane ? attachmentPane : documentBody).find('#iframeONE')[0];
					$(iframe).on('load', function () {
						setTimeout(function () {
							var a = $('<a>', { href: iframe.src })[0];
							var url = a.origin ? a.origin : (a.protocol + "//" + a.host.replace(":80", "").replace(":443", ""));
							var ifr = iframe.contentWindow ? iframe.contentWindow : iframe.contentDocument.defaultView;
							ifr.postMessage("SETTIME:" + secs, url);
						}, 100);
					});
				}
			}
		}

		return false;
	};

	this.resizeVideo = function () {
		setVideoSize();
	};

	var setVideoSize = function () {
		if (documentBody) {
			var bodyWidth = (attachmentPane ? attachmentPane : documentBody).width();
			var videoWidth = (!isNaN(bodyWidth) ? parseFloat(bodyWidth) : minWidthChromeLoad4x3) * videoScale;
			if (videoWidth > maxVideoWidth) {
				videoWidth = maxVideoWidth;
			}
			var videoHeight = videoWidth * videoRatio[currentVideo];

			if (youTube && youTubeEventId.length > 0) {

				if (attachmentPane == null)
				{
					documentBody.css({ 'padding-top': videoHeight + 10 + 'px' });
				}

				(attachmentPane ? attachmentPane : documentBody).find('#timeStampVideoDiv').attr('width', videoWidth + 'px').attr('height', videoHeight + 'px');//.css({ 'width': '94%' });
				(attachmentPane ? attachmentPane : documentBody).find('#videoDiv').attr('width', videoWidth + 'px').attr('height', videoHeight + 'px');//.css({ 'width': '94%' });
			}
			else {
				(attachmentPane ? attachmentPane : documentBody).find('#iframeONE').attr('width', videoWidth).attr('height', videoHeight);
			}
		}
	};

	var setVideoWidthHeight = function (currentVideoRatio) {
		var bodyWidth = (attachmentPane ? attachmentPane : documentBody).width();
		videoWidth = (!isNaN(bodyWidth) ? parseFloat(bodyWidth) : minWidthChromeLoad4x3) * videoScale;

		if (videoWidth > maxVideoWidth) {
			videoWidth = maxVideoWidth;
		}

		if (videoWidth < minWidthChromeLoad4x3 && navigator.userAgent.indexOf('Chrome') != -1 && currentVideoRatio == ratio4x3 && !youTube) {
			//4:3
			videoWidth = minWidthChromeLoad4x3;
			(attachmentPane ? attachmentPane : documentBody).attr('width', minWidthChromeLoad4x3);
		}
		else if (videoWidth < minWidthChromeLoad16x9 && navigator.userAgent.indexOf('Chrome') != -1 && currentVideoRatio == ratio16x9 && !youTube) {
			//16:9
			videoWidth = minWidthChromeLoad16x9;
			(attachmentPane ? attachmentPane : documentBody).attr('width', minWidthChromeLoad16x9);
		}

		videoHeight = videoWidth * currentVideoRatio;
	};

	function sleep(ms) {
		return new Promise(function (resolve) { setTimeout(resolve, ms) });
	};

	var getTime = function (callback) {
		if (youTube && window.myPlayer != null) {
			callback(0, Math.round(window.myPlayer.getCurrentTime()), true);
		}
		else {
			callback(0, 0, true);
		}
	};

	var setTime = function (secs, i) {
		if (youTube && window.myPlayer != null) {
			if (window.myPlayer.seekTo) {
				window.myPlayer.seekTo(secs);
			}
			else {
				if (i < 20) {
					i++;
					sleep(100).then(function () { return setTime(secs, i); });
				}
			}
		}
	};

	this.moveVideoToAgendaFrame = function (moveBackToAttachmentFrame, i) {
		if (documentBody == null && i < 20) {
			i++;
			setTimeout(function () { CivicWeb.Integration.Video.moveVideoToAgendaFrame(moveBackToAttachmentFrame, i); }, 100);
		}
		else {
			moveVideoToAgendaFrame(moveBackToAttachmentFrame);
		}

	};

	var moveVideoToAgendaFrame = function (moveBackToAttachmentFrame) {
		//only if it's in the Attachment frame
		if (documentBody && documentBody.find('#videoDiv').length == 0)// && $('#video-button').find('span[class="toolbar-text"]').text() == localization.hideLabel)
		{
			getTime(
				function (id, secs, hyphen) {
					hideVideo();

					//if (moveBackToAttachmentFrame)
					//{
					videoScale = 0.618;
					maxVideoWidth = 505;
					//}

					if (attachmentPane != null) {
						attachmentPane.find('#attachment-container').removeClass('hidden');
						attachmentPane = null;
					}

					setVideoWidthHeight(videoRatio[currentVideo]);

					showVideo();
					setTimeout(function () { setTime(secs, 1); }, 100);

					if (moveBackToAttachmentFrame) {
						$('#video-button').off('click').on('click', moveVideoToAttachmentFrame).removeClass("hidden").find('span[class="toolbar-text"]').text(localization.audioVideoLabel).attr('title', localization.showAudioVideoLabel + ' in the attachment pane');;
					}
					else {
						$('#video-button').off('click').on('click keypress', hideVideo).on('keypress', function (event) {
							if (event.which == 13 || event.which == 32) {
								hideVideo(event);
								return;
							}
						}).attr({ 'title': localization.hideAudioVideoLabel, 'aria-label': localization.hideAudioVideoLabel }).find('span[class="toolbar-text"]').text(localization.hideLabel);
					}

				}
			);
		} else {
			attachmentPane = null;
			$('#video-button').off('click').on('click', showVideo).find('span[class="toolbar-text"]').text(localization.audioVideoLabel);
		}
	};

	this.moveVideoToAttachmentFrame = function () {
		moveVideoToAttachmentFrame();
	};

	var moveVideoToAttachmentFrame = function () {
		if (documentBody && documentBody.find('#videoDiv').length > 0) {
			//only if it's in the Agenda frame
			getTime(
				function (id, secs, hyphen) {
					hideVideo();

					attachmentPane = $('#attachment-pane');
					if (attachmentPane.length == 0 && window.parent.$) {
						attachmentPane = window.parent.$('#attachment-pane');
					}

					if (attachmentPane.length > 0) {
						videoScale = 1;
						maxVideoWidth = 800;

						setTimeout(function () {
							setVideoWidthHeight(videoRatio[currentVideo]);
							showVideo();
							setTimeout(function () { setTime(secs, 1); }, 100);
						}, 0);
					}
					else {
						attachmentPane = null;
					}
				}
			);

		}
	};

	var showVideo = function (e) {
		(attachmentPane ? attachmentPane : documentBody).find('#videoDiv').remove();
		if (videoElement.length > 0 && documentBody != null) {
			if (navigator.userAgent.indexOf('Chrome') != -1) {
				var iframeBodyInitialWidth = (attachmentPane ? attachmentPane : documentBody).width();
				var minWidthToLoadChrome = minWidthChromeLoad16x9;
				if (iframeBodyInitialWidth < (minWidthChromeLoad4x3) && videoRatio[currentVideo] == ratio4x3) {
					minWidthToLoadChrome = minWidthChromeLoad4x3;
				}
				else if (iframeBodyInitialWidth < (minWidthChromeLoad16x9) && videoRatio[currentVideo] == ratio16x9) {
					minWidthToLoadChrome = minWidthChromeLoad16x9;
				}
				if (iframeBodyInitialWidth < minWidthToLoadChrome) {
					$(document.getElementById('AgendaPane')).width(minWidthToLoadChrome + 25);
					if (!eventIsYouTubeVideo(youTubeEventId))
					{
						$('body').prepend(videoElement[currentVideo]);
						loadBoxCastVideo('videoDiv', youTubeEventId);
					}
					else if (youTube && youTubeEventId.length > 0) {
						$('body').prepend(videoElement[currentVideo]);
						loadYouTubeVideo('videoDiv');
					}
					else {
						(attachmentPane ? attachmentPane : documentBody).prepend(videoElement[currentVideo]);
					}

					iframeBodyInitialWidth = iframeBodyInitialWidth < (earthChannelForcedMinHeight / videoRatio[currentVideo]) ? (earthChannelForcedMinHeight / videoRatio[currentVideo]) : iframeBodyInitialWidth;
					//wait till loaded
					setTimeout(function () { $(document.getElementById('AgendaPane')).width(iframeBodyInitialWidth + 25); setVideoSize() }, 1000);

				}
				else {
					if (!eventIsYouTubeVideo(youTubeEventId))
					{
						$('body').prepend(videoElement[currentVideo]);
						loadBoxCastVideo('videoDiv', youTubeEventId);
					}
					else if (youTube && youTubeEventId.length > 0) {
						$('body').prepend(videoElement[currentVideo]);
						loadYouTubeVideo('videoDiv');
					}
					else {
						(attachmentPane ? attachmentPane : documentBody).prepend(videoElement[currentVideo]);
					}
				}
			}
			else {
				if (!eventIsYouTubeVideo(youTubeEventId))
				{
					$('body').prepend(videoElement[currentVideo]);
					loadBoxCastVideo('videoDiv', youTubeEventId);
				}
				else if (youTube && youTubeEventId.length > 0) {
					$('body').prepend(videoElement[currentVideo]);
					loadYouTubeVideo('videoDiv');
				}
				else {
					(attachmentPane ? attachmentPane : documentBody).prepend(videoElement[currentVideo]);
				}
			}

			$(documentBody.find('body')).css({ 'margin-right': '15px' });

			$('#video-button').off('click keypress').on('click', hideVideo).on('keypress', function (event) {
				if (event.which == 13 || event.which == 32) {
					hideVideo(event);
					return;
				}
			}).attr({ 'title': localization.hideAudioVideoLabel, 'aria-label': localization.hideAudioVideoLabel }).find('span[class="toolbar-text"]').text(localization.hideLabel);

			if (!youTube) {
				resizeVideoDiv(e);
			}
		}
		else if (historic) {
			window.open(urlBase[currentVideo], '_blank', "toolbar=no,scrollbars=no,resizable=no,top=50,left=50,width=1000,height=770");
		}
		if (attachmentPane) {
			attachmentPane.find('#attachment-container').addClass('hidden');
		}
		if (window.parent && window.parent.$) {
			window.parent.$('#walkme-player').hide();
		}
		//when auto playing this isn't a button click and e is null!!!!!
		if (e != null) {
			e.preventDefault();
		}
		return false;
	};

	this.hideVideo = function (e) {
		hideVideo(e);
	}

	var hideVideo = function (e) {
		if (documentBody != null) {
			currentVideo = 0;
			youTubeEventId = youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo].eventId != null ? youTubeEvents[currentVideo].eventId : '';

			if (youTube) {
				myVideoWindow = null;
				$(document.getElementById('timeStampVideoDiv')).closest('.k-window').remove();
			}

			(attachmentPane ? attachmentPane : documentBody).find('#videoDiv').remove();
			documentBody.css({ 'margin-right': '0' });

			$('#video-button').off('click keypress').on('click', showVideo).on('keypress', function (event) {
				if (event.which == 13 || event.which == 32) {
					showVideo(event);
					return;
				}
			}).attr({ 'title': localization.showAudioVideoLabel, 'aria-label': localization.showAudioVideoLabel }).find('span[class="toolbar-text"]').text(localization.audioVideoLabel);

			//this should return the scrollable agenda content area to be non-scrollable
			(attachmentPane ? attachmentPane : documentBody).css({ 'padding-top': '' });
			if (typeof CivicWeb != 'undefined' && typeof CivicWeb.Document != 'undefined' && typeof CivicWeb.Document.AgendaNotesPage != 'undefined' && CivicWeb.Document.AgendaNotesPage.getInstance() != null) {
				CivicWeb.Document.AgendaNotesPage.events.resizeAgendaDocument(e);
			}
		}

		if (attachmentPane) {
			attachmentPane.find('#attachment-container').removeClass('hidden');
		}

		if (e != null) {
			e.preventDefault();
		}
		return false;
	};

	var resizeVideoDiv = function (e) {
		//this is the sizing of the scrollable agenda area
		//HTML quick-view
		if (documentBody.length > 0) {
			if (attachmentPane) {
				attachmentPane.find('#videoDiv').css({ 'top': '0', 'background-color': 'white', 'z-index': '600', 'position': '', 'height': '99.83%' });
			}
			else {
				documentBody.css({ 'padding-top': videoHeight + 10 + 'px' });
				documentBody.find('#videoDiv').css({ 'position': 'fixed', 'top': '0', 'width': '100%', 'background-color': 'white', 'z-index': '600' });
			}
			if (agendaDocument && typeof CivicWeb != 'undefined' && typeof CivicWeb.Document != 'undefined' && typeof CivicWeb.Document.AgendaNotesPage != 'undefined' && CivicWeb.Document.AgendaNotesPage.getInstance() != null) {
				CivicWeb.Document.AgendaNotesPage.events.resizeAgendaDocument(e);
			}
		}
	}

	this.convertSecondsToTimeString = function (secs, hyphens, itemId) {
		return convertSecondsToTimeString(secs, hyphens, itemId);
	};

	var convertSecondsToTimeString = function (secs, hyphens, itemId, timeStampEvent) {
		var timestamp = '';
		var leading = hyphens ? '-' : '0';
		if (secs >= 3600) {
			var h = Math.floor(secs / 3600);
			var m = Math.floor(secs % 3600 / 60);
			var s = Math.floor(secs % 3600 % 60);
			timestamp = h < 10 ? (hyphens ? leading : '') + h + 'h' : h + 'h';
			timestamp += m < 10 ? '0' + m + 'm' : m + 'm';
			timestamp += s < 10 ? '0' + s + 's' : s + 's';

		}
		else if (secs >= 60) {
			var m = Math.floor(secs / 60);
			var s = (secs % 60);
			timestamp = (hyphens ? leading + leading : leading) + 'h';
			timestamp += m < 10 ? leading + m + 'm' : m + 'm';
			timestamp += s < 10 ? '0' + s + 's' : s + 's';

		}
		else {
			var s = (secs % 60);
			timestamp = (hyphens ? leading + leading : leading) + 'h' + leading + leading + 'm';
			timestamp += s < 10 ? leading + s + 's' : s + 's';

		}

		if (itemId != null && eventIds.length > 1) {
			var timeStampEventId = timeStampEvent != null ? timeStampEvent : (BuildForms != null ? BuildForms.GetItemValue(itemId, referenceFieldLocalization.videoTimeStampEventFieldReferenceName) : '');
			var index = eventIds.indexOf(timeStampEventId) + 1;
			if (index > 0) {
				timestamp = 'Part ' + index + ': ' + timestamp;
			}
		}

		return timestamp;
	};

	/////////////////////////////////////////////////////////////////////////////////////
	//Minutes --------------------------------------------------------------------------
	var setUpMinutesToTimeStamp = function (meetingId) {
		$.ajax({
			url: '/api/geteventwithindexpoints/' + meetingId.toString(),
			contentType: 'application/json', dataType: 'json', async: true, cache: false, type: 'GET',
			success: function (result) {
				if (result) {
					urlBase = [];
					eventIds = [];

					for (var k = 0; k < result.length; k++) {
						var dat = result[k];
						var event = dat.Event != null ? dat.Event : null;
						var eventId = event != null && event.eventId != null ? event.eventId : '';
						if (eventIds.indexOf(eventId) == -1) {
							eventIds.push(eventId);
						}
					}

					for (var i = 0; i < result.length; i++) {
						var d = result[i];
						liveTimestamping = d.PublisherEvent ? d.PublisherEvent.MediaType.toLowerCase() == 'live' : false;
						var isMediaEnabled = d.PublisherEvent ? d.PublisherEvent.IsMediaEnabled : false;
						var publisherEventId = d.PublisherEvent ? d.PublisherEvent.PublisherEventID : 0;
						var event = d.Event != null ? d.Event : null;
						var eventId = event != null && event.eventId != null ? event.eventId : '';
						//var eventTitle = events != null && events.eventTitle != null ? events.eventTitle : '';

						if ((isMediaEnabled && publisherEventId > 0) || (eventId.length > 0 && eventId != '0')) {
							videoRatio.push((d.PublisherEvent && (parseInt(d.PublisherEvent.EnabledItemMask) & 4096) > 0) ? ratio16x9 : ratio4x3);

							if (event != null) {
								youTubeEvents.push(event);
							}

							var localIndexPoints = d.LocalIndexPoints ? d.LocalIndexPoints : null;
							if (localIndexPoints) {
								for (var j = 0; j < localIndexPoints.length; j++) {
									var itemId = localIndexPoints[j].ItemId;
									var secondsStart = localIndexPoints[j].Value;
									var timestampEvent = localIndexPoints[j].Event;

									if (secondsStart != null && !isNaN(secondsStart)) {
										if (secondsStart < 0) {
											timeString = '<a href"#" style="color:red;" class="time-stamp-event-link" time-stamp-event="' + timestampEvent + '" time-stamp="' + secondsStart + '" onclick="CivicWeb.Integration.Video.gotoMinutesVideoTimeStamp(this)">' + '-' + CivicWeb.Integration.Video.convertSecondsToTimeString(Math.abs(secondsStart), false, itemId) + '</a>';
										}
										else {
											timeString = '<a href"#" class="time-stamp-event-link" time-stamp-event="' + timestampEvent + '" time-stamp="' + secondsStart + '" onclick="CivicWeb.Integration.Video.gotoMinutesVideoTimeStamp(this)">' + CivicWeb.Integration.Video.convertSecondsToTimeString(secondsStart, false, itemId) + '</a>';
										}

										var timestampField = $(document.getElementById(referenceFieldLocalization.videoTimeStampFieldReferenceName + '_' + itemId));
										if (timestampField.length > 0) {
											timestampField.html(timeString);
										}
									}
								}
							}

							//Set Min size so video auto plays
							if (!youTube && navigator.userAgent.indexOf('Chrome') != -1) {
								if (videoRatio[0] == ratio4x3) {
									//4:3
									videoWidth = minWidthChromeLoad4x3;
									videoHeight = videoWidth * videoRatio[currentVideo];
								}
								else if (videoRatio[0] == ratio16x9) {
									//16:9
									videoWidth = minWidthChromeLoad16x9;
									videoHeight = videoWidth * videoRatio[currentVideo];
								}
							} else {
								videoHeight = earthChannelForcedMinHeight;
								videoWidth = videoHeight / videoRatio[currentVideo];
							}

							urlBase.push((d.PublisherEvent ? d.PublisherEvent.URLBase.replace('http://view.earthchannel.com/PlayerController.aspx', '//viewer.earthchannel.com/PlayerMedia.aspx') : '') + '&amp;eID=' + publisherEventId + '&amp;mode=embed');

							if (liveTimestamping) {
								$('#timeStampVideoButton').removeClass('hidden').attr({ 'title': (audioOnly ? 'Play the live stream' : 'View the live stream') }).off('click').on('click', toggleTimeStampVideo).find('span').text((audioOnly ? 'Play Stream' : 'View Stream'));
							}
							else {
								$('#timeStampVideoButton').removeClass('hidden').off('click').on('click', toggleTimeStampVideo);

								if (manageVideo && timestampEnabled) {
									$('#timeStampSyncVideo').removeClass('hidden').off('click').on('click', toggleTimeStampSyncMode);
								}
							}
						}
					}
					youTubeEventId = youTubeEvents.length > 0 && youTubeEvents[0] != null && youTubeEvents[0].eventId != null ? youTubeEvents[0].eventId : '';
				}
				else {

				}
			},
			error: function () {
				//return '';
			}
		});

	};

	this.gotoMinutesVideoTimeStamp = function (e) {
		gotoMinutesVideoTimeStamp(e);
	};

	var gotoMinutesVideoTimeStamp = function (e) {
		var secs = $(e).attr('time-stamp');
		secs = !isNaN(secs) ? parseInt(secs) : 0;
		secs = secs < 0 ? '0' : secs.toString();

		if (youTube && window.myPlayer != null) {
			var timeStampEvent = $(e).attr('time-stamp-event');
			if (timeStampEvent != null && timeStampEvent != youTubeEventId) {
				youTubeEventId = timeStampEvent;
				window.myPlayer.loadVideoById(timeStampEvent, secs, "large");
				updateEventDropDown();
			}
			else {
				window.myPlayer.seekTo(secs);
			}
		}
		else {
			var iframe = $('#timeStampVideoDiv').find('iframe')[0];
			if (iframe) {
				var a = $('<a>', { href: iframe.src })[0];
				var url = a.origin ? a.origin : (a.protocol + "//" + a.host.replace(":80", "").replace(":443", ""));
				var ifr = iframe.contentWindow ? iframe.contentWindow : iframe.contentDocument.defaultView;
				ifr.postMessage("SETTIME:" + secs, url);
			}
		}
		return false;
	};

	this.toggleTimeStampSyncMode = function () {
		toggleTimeStampSyncMode();
	};

	var toggleTimeStampSyncMode = function () {
		var timeStampSyncVideo = $('#timeStampSyncVideo');
		if (!syncModeEnabled && confirm('Sync mode allows timestamps to be synced with the recorded ' + (audioOnly ? 'audio' : 'video') + '. Sync mode affects all timestamps related to the video.\nDo you want to continue?')) {
			timeStampSyncVideo.attr({ 'title': 'Disable Sync Mode' }).find('span').text('Disable Sync Mode');
			$('#subMenu').append('<b id="syncModeEnabledLabel" style="float: right; margin-right: 2em; padding-right: 3px; background-color: #296498; color: #fff;" >Sync Mode Enabled</b>');
			syncModeEnabled = true;

			if ($(document.getElementById('timeStampVideoDiv')).length == 0) {
				toggleTimeStampVideo();
			}
		}
		else {
			timeStampSyncVideo.attr({ 'title': 'Sync timestamps with recorded ' + (audioOnly ? 'audio' : 'video') }).find('span').text('Enable Sync Mode');
			$('#syncModeEnabledLabel').remove();
			syncModeEnabled = false;
		}

		if (ATMBuild.SelectedItem != null) {
			Build.AddVideoTimeStampButton(ATMBuild.SelectedItem);
		}
	};

	var toggleTimeStampVideo = function () {
		if (CivicWeb.Common.loadKendoUi(toggleTimeStampVideo)) {
			if (!myVideoWindow) {
				$('body').prepend('<div id="timeStampVideoDiv"/>');

				var kendoVideoWindow = $(document.getElementById('timeStampVideoDiv'))
				kendoVideoWindow.css({ 'margin': '0', 'padding': '0' }).kendoWindow({
					width: videoWidth + 'px',
					height: videoHeight + 'px',
					title: 'Timestamp ' + (audioOnly ? 'Audio' : 'Video'),
					modal: false,
					visible: true,
					resizable: false,
					actions: ['Close'],
					content: urlBase[currentVideo],
					close: closeKendoVideoWindow,
					position: { top: 0, left: 0 },
					id: "kendoVideoWindow"
				})

				setTimeout(function () {
					var timeStampVideoDiv = $(document.getElementById('timeStampVideoDiv'));

					if (youTube) {
						timeStampVideoDiv.height(earthChannelForcedMinHeight);
						timeStampVideoDiv.width(earthChannelForcedMinHeight / videoRatio[currentVideo]);
					}
					else {
						timeStampVideoDiv.parent().height(earthChannelForcedMinHeight);
						timeStampVideoDiv.parent().width(earthChannelForcedMinHeight / videoRatio[currentVideo]);
					}
				}, 1000);


				myVideoWindow = $(document.getElementById('timeStampVideoDiv')).data("kendoWindow");
				$(document.getElementById('timeStampVideoDiv')).closest('.k-window').css({ 'position': 'fixed', 'top': '0', 'left': '0' });
				myVideoWindow.open();
				$('#timeStampVideoButton').attr({ 'title': (liveTimestamping ? (audioOnly ? 'Stop playing the stream' : 'Stop viewing the stream') : (audioOnly ? 'Stop playing the audio' : 'Stop viewing the video')) }).find('span').text((liveTimestamping ? 'Stop Stream' : (audioOnly ? 'Stop Audio' : 'Close video popup')));

				if (youTube && CivicWeb.Integration.Video.getCurrentEvent() != null) {
					loadYouTubeVideo('timeStampVideoDiv');

					updateEventDropDown();
				}
			}
			else {
				closeKendoVideoWindow();
				$('#timeStampVideoButton').attr({ 'title': (liveTimestamping ? (audioOnly ? 'Play the live stream' : 'View the live stream') : (audioOnly ? 'Play the recorded audio' : 'View the recorded video')) }).find('span').text(liveTimestamping ? (audioOnly ? 'Play Stream' : 'View Stream') : (audioOnly ? 'Play Audio' : 'View Video'));
			}
		}
	};

	var closeKendoVideoWindow = function () {
		myVideoWindow = null;
		$(document.getElementById('timeStampVideoDiv')).closest('.k-window').remove();
		$('#timeStampVideoButton').attr({ 'title': (liveTimestamping ? (audioOnly ? 'Play the live stream' : 'View the live stream') : (audioOnly ? 'Play the recorded audio' : 'View the recorded video')) }).find('span').text(liveTimestamping ? (audioOnly ? 'Play Stream' : 'View Stream') : (audioOnly ? 'Play Audio' : 'View Video'));

		if (syncModeEnabled) {
			$('#timeStampSyncVideo').attr({ 'title': 'Sync timestamps with recorded ' + (audioOnly ? 'audio' : 'video') }).find('span').text('Enable Sync Mode');
			$('#syncModeEnabledLabel').remove();
			syncModeEnabled = false;
		}
	};

	var saveVideoEventSettings = function (events, startAtFirstTimestamp) {
		var obj = {};
		obj.MeetingId = meetingId;
		obj.Events = events;
		obj.StartAtFirstTimestamp = startAtFirstTimestamp;

		$.ajax({
			url: '/api/savevideoeventsettings',
			contentType: 'application/json',
			dataType: 'json',
			async: true,
			cache: false,
			type: 'POST',
			data: JSON.stringify(obj),
			success: function (response) {
				setTimeout(function () {
					$('#videoevent-selector-container').slideUp();

					$('#earthChannelEventLink').remove();
					$('#showVideoLinkSpan').remove();
					$('#showTimeStampsSpan').remove();

					$('#timeStampVideoButton').addClass('hidden');
					$('#timeStampSyncVideo').addClass('hidden');

					$('.time-stamp-event-link').remove();

					if (manageVideo && meetingId != null && meetingId > 0) {
						setUpViewCreateEventLink(meetingId);
					}

					if (minutesBuild) {
						setUpMinutesToTimeStamp(meetingId);
					}
				}, 750);
			},
			error: function () {
				//return '';
			}
		});
	};

	var toggleshowVideoLink = function (e) {
		var obj = {};
		obj.MeetingId = meetingId;

		var id = $(e).attr('id');
		var confirmMsg = '';
		var checkedShowVideo = false;
		var showTimestampsFlipped = false;
		if (id == 'showVideoLink') {
			obj.ShowVideoLink = e.checked;
			if (!e.checked) {
				$('#showTimeStamps').prop('checked', false);
				obj.ShowTimeStamps = false;
				showTimestampsFlipped = true;
			}
			else {
				obj.ShowTimeStamps = $('#showTimeStamps').prop('checked');
			}

			confirmMsg = (e.checked ? 'Show' : 'Hide') + ' the ' + (audioOnly ? 'audio' : 'video') + ' button on the published agenda and minutes?\nDo you want to continue?';
		}
		else if (id == 'showTimeStamps') {
			obj.ShowTimeStamps = e.checked;
			if (!$('#showVideoLink').prop('checked')) {
				checkedShowVideo = true;
			}
			$('#showVideoLink').prop('checked', true);
			obj.ShowVideoLink = true;
			confirmMsg = (e.checked ? 'Show' : 'Hide') + ' the timestamps on the published agenda and minutes?\nDo you want to continue?';
		}

		if (confirm(confirmMsg)) {
			$.ajax({
				url: '/api/savevideoeventsettings',
				contentType: 'application/json',
				dataType: 'json',
				async: true,
				cache: false,
				type: 'POST',
				data: JSON.stringify(obj),
				success: function (response) {

				},
				error: function () {
					//return '';
				}
			});
		}
		else {
			e.checked = !e.checked;
			if (id == 'showVideoLink' && showTimestampsFlipped) {
				$('#showTimeStamps').prop('checked', e.checked);
			}

			if (checkedShowVideo) {
				$('#showVideoLink').prop('checked', false);
			}
		}

	};

	this.getSyncMode = function () {
		return syncModeEnabled;
	};

	this.isAudioOnly = function () {
		return audioOnly;
	};

	this.isLive = function () {
		return liveTimestamping;
	};

	var setUpViewCreateEventLink = function (id) {
		$.ajax({
			url: '/api/getevent/' + id.toString(),
			contentType: 'application/json', dataType: 'json', async: true, cache: false, type: 'GET',
			success: function (result) {
				var data = JSON.parse(result);
				var displayShowVideoLinkCheckbox = data.DisplayShowVideoLinkCheckbox != null ? data.DisplayShowVideoLinkCheckbox : false;
				var showVideoLink = data.ShowVideoLink != null ? data.ShowVideoLink : false;
				var showTimeStamps = data.ShowTimeStamps != null ? data.ShowTimeStamps : false;
				var historic = data.Historic != null ? data.Historic : false;
				var validYouTubeCredentialExists = data.validYouTubeCredentialExists != null ? data.validYouTubeCredentialExists : false;
				var publicDocumentExists = data.publicDocumentExists != null ? data.publicDocumentExists : false;
				var meetingId = data.MeetingId != null ? data.MeetingId : 0;
				var meetingName = data.MeetingName != null ? data.MeetingName : '';
				var meetingDateInThePast = data.MeetingDateInThePast != null ? data.MeetingDateInThePast : false;
				var meetingStartTimeExists = data.MeetingStartTimeExists != null ? data.MeetingStartTimeExists : false;

				var eventId = data.eventId != null ? data.eventId : '';
				var events = data.Events != null ? data.Events : [];
				var startAtFirstTimestamp = data.StartAtFirstTimestamp != null ? data.StartAtFirstTimestamp : false;
				var boxcast = data.boxcast != null ? data.boxcast : false;
				var broadcasts = data.broadcasts != null ? data.broadcasts : [];
				var boxcasters = data.boxcasters != null ? data.boxcasters : [];
				var rtmpSources = data.rtmpSources != null ? data.rtmpSources : [];
				var youtubeAccounts = data.youtubeAccounts != null ? data.youtubeAccounts : [];

				var eventLink = $('<a/>');
				if (youTube && eventId != '-1') {
					eventLink.attr({ 'id': 'earthChannelEventLink', 'class': 'subMenuText', 'href': '' }).text('Video').off('click').on('click', function (e) { closeYouTubeVideoEventSelector(); openYouTubeVideoEventSelector(e, meetingName, events, meetingDateInThePast, meetingStartTimeExists, startAtFirstTimestamp, boxcast, broadcasts, boxcasters, youtubeAccounts, rtmpSources); e.preventDefault(); });
					eventLink.attr({ 'title': (youTubeLite ? 'Paste in the YouTube link to connect to this meeting instance' : (boxcast ? 'Select a broadcast or create a new broadcast to connect to this meeting' : 'Select the YouTube live stream or a recorded video to connect to this meeting instance.')) });
				}
				else {
					eventLink.attr({ 'id': 'earthChannelEventLink', 'class': 'subMenuText', 'href': ('/videologin/' + meetingId + '/' + (eventId == '-1' ? '0' : eventId)), 'target': '_blank' });
					if (eventId != '0' && eventId != '-1') {
						eventLink.text(viewEvent);
					}
					else {
						eventLink.text(createEvent);
					}
				}

				if (eventId == '-1') {
					if (!publicDocumentExists) {
						eventLink.text((youTube ? 'Video' : createEvent)).addClass('disableCreateEventLink').attr({ 'disabled': 'disabled', 'title': 'A public Agenda needs to be published before ' + (boxcast ? 'a broadcast can be connected' : (youTube ? 'a video can be connected' : 'an event can be created')) }).removeAttr('href target');
						if (youTube) {
							eventLink.off('click').on('click', function (e) { if ($(this).attr('disabled')) { return false; }; closeYouTubeVideoEventSelector(); openYouTubeVideoEventSelector(e, meetingName, [], meetingDateInThePast, meetingStartTimeExists, startAtFirstTimestamp, boxcast, broadcasts, boxcasters, youtubeAccounts); e.preventDefault(); });
						}
					}
					else if (youTube && !validYouTubeCredentialExists) {
						eventLink.text('Video').addClass('disableCreateEventLink').attr({ 'title': 'Valid YouTube credentials are needed before an event can be created. Add credentials under the admin area on the General Settings page.' }).removeAttr('href target');
					}
				}

				$('#subMenu').append(eventLink);

				if (eventId != '0' && eventId != '-1' && displayShowVideoLinkCheckbox) {
					var showVideoContainer = $('<span/>').attr({ 'id': 'showVideoLinkSpan', 'title': 'Show the ' + (audioOnly ? 'audio' : 'video') + ' button on the published agenda and minutes documents' });
					showVideoContainer.append($('<input/>').attr({ 'id': 'showVideoLink', 'type': 'checkbox', 'checked': showVideoLink }).css({ 'margin-left': '2em', 'vertical-align': 'middle' }).off('click').on('click', function () { toggleshowVideoLink(this); }));
					showVideoContainer.append($('<label/>').attr({ 'for': 'showVideoLink' }).css({ 'text-indent': '0px' }).text('Show ' + (audioOnly ? 'Audio' : 'Video') + ' Button'));
					$('#subMenu').append(showVideoContainer);

					if (!historic) {
						var showTimeStampsContainer = $('<span/>').attr({ 'id': 'showTimeStampsSpan', 'title': 'Show timestamps on the published agenda and minutes documents' });
						showTimeStampsContainer.append($('<input/>').attr({ 'id': 'showTimeStamps', 'type': 'checkbox', 'checked': showTimeStamps }).css({ 'margin-left': '2em', 'vertical-align': 'middle' }).off('click').on('click', function () { toggleshowVideoLink(this); }));
						showTimeStampsContainer.append($('<label/>').attr({ 'for': 'showTimeStamps' }).css({ 'text-indent': '0px' }).text('Show Timestamps'));
						$('#subMenu').append(showTimeStampsContainer);
					}
				}

				if (minutesBuild && meetingId > 0 && broadcasts.length > 0)
				{
					addBoxCastInCameraButton(broadcasts, meetingId);
				}
				else
				{
					$('#boxcaster-incamera-control').addClass('hidden');
				}
			},
			error: function () {
				//return '';
			}
		});
	};

	/////////////////////////////////////////////////////////////////////////////////////
	//YouTube --------------------------------------------------------------------------

	var closeYouTubeVideoEventSelector = function ()
	{
		nextPageToken = "";
		$('#videoevent-selector-container').remove();
	};

	var showInCameraButton = function (meetingId, currentlyInCamera)
	{
		$('#boxcaster-incamera-control').removeClass('hidden');
		if (currentlyInCamera)
		{
			$('#OpenSession').removeClass('hidden').off('click').on('click', function (e) { setInCameraSession(e, meetingId, false); });
		}
		else
		{
			$('#ClosedSession').removeClass('hidden').off('click').on('click', function (e) { setInCameraSession(e, meetingId, true); });
		}
	}

	var addInCameraButton = function (broadcastDetails, meetingId)
	{
		if (broadcastDetails && broadcastDetails.length > 0)
		{
			var currentlyInCamera = false;
			var minimuMillisecondsToStart = Number.MAX_SAFE_INTEGER;
			var allBroadcastsEnded = true;

			for (var i = 0; i < broadcastDetails.length; i++)
			{
				var broadcastDetail = broadcastDetails[i];

				if ((broadcastDetail.metadata.mixer != null && broadcastDetail.metadata.mixer.muted) || (broadcastDetail.metadata.overlays != null && broadcastDetail.metadata.overlays.length > 0))
				{
					currentlyInCamera = true;
				}

				minimuMillisecondsToStart = broadcastDetail.millisecondsToStart < minimuMillisecondsToStart ? broadcastDetail.millisecondsToStart : minimuMillisecondsToStart;
				allBroadcastsEnded = allBroadcastsEnded && broadcastDetail.streamEnded;
			}

			if (!allBroadcastsEnded)
			{
				if (minimuMillisecondsToStart > 0)
				{
					setTimeout(function () { showInCameraButton(meetingId, currentlyInCamera); }, minimuMillisecondsToStart);
				}
				else
				{
					showInCameraButton(meetingId, currentlyInCamera);
				}
			}
		}
	}

	var addBoxCastInCameraButton = function (broadcasts, meetingId)
	{
		var obj = {};
		obj.Broadcasts = broadcasts;
		obj.meetingId = meetingId;

		$.ajax({
			url: '/api/broadcastdetails',
			contentType: 'application/json',
			dataType: 'json',
			async: true,
			cache: false,
			type: 'POST',
			data: JSON.stringify(obj),
			success: function (response)
			{
				addInCameraButton(response, meetingId);
			},
			error: function ()
			{
				addInCameraButton(false, meetingId);
			}
		});
	}

	var setInCameraSession = function (e, meetingId, incamera)
	{
		if (incamera)
		{
			$('#ClosedSession').attr('disabled', true);
			$('#loadingSpinnerClosed').removeClass('hidden');
		}
		else
		{	
			$('#OpenSession').attr('disabled', true);
			$('#loadingSpinnerOpen').removeClass('hidden');
		}

		var obj = {};
		obj.MeetingId = meetingId;
		obj.InCamera = incamera;

			$.ajax({
				url: '/api/toggleboxcastintermission',
				contentType: 'application/json',
				dataType: 'json',
				async: true,
				cache: false,
				type: 'POST',
				data: JSON.stringify(obj),
				success: function (response)
				{
					$('#loadingSpinnerOpen').addClass('hidden');
					$('#loadingSpinnerClosed').addClass('hidden');
					if (response.success && incamera)
					{
						$('#OpenSession').removeClass('hidden').off('click').on('click', function (e) { setInCameraSession(e, meetingId, false); });
						$('#ClosedSession').addClass('hidden').attr('disabled', false).off('click').on('click', function (e) { setInCameraSession(e, meetingId, true); });
					}
					else if (response.success && !incamera)
					{
						$('#ClosedSession').removeClass('hidden').off('click').on('click', function (e) { setInCameraSession(e, meetingId, true); });
						$('#OpenSession').addClass('hidden').attr('disabled', false).off('click').on('click', function (e) { setInCameraSession(e, meetingId, false); });
					}
					else
					{
						$('#ClosedSession').attr('disabled', false).off('click').on('click', function (e) { setInCameraSession(e, meetingId, true); });
						$('#OpenSession').attr('disabled', false).off('click').on('click', function (e) { setInCameraSession(e, meetingId, false); });
						alert("There was an error setting the broadcast to " + (incamera ? "intermission" : "public"));
					}
				},
				error: function ()
				{
					$('#loadingSpinnerOpen').addClass('hidden');
					$('#loadingSpinnerClosed').addClass('hidden');
					$('#ClosedSession').attr('disabled', false).off('click').on('click', function (e) { setInCameraSession(e, meetingId, true); });;
					$('#OpenSession').attr('disabled', false).off('click').on('click', function (e) { setInCameraSession(e, meetingId, false); });;
					alert("There was an error setting the broadcast to " + (incamera ? "intermission" : "public"));
				}
			});


		e.preventDefault();
	}

	var openYouTubeVideoEventSelector = function (e, meetingName, events, meetingDateInThePast, meetingStartTimeExists, startAtFirstTimestamp, boxcast, broadcasts, boxcasters, youtubeAccounts, rtmpSources)
	{
		//window
		var videoSelectorWindow = $('<div/>').attr({ 'id': 'videoevent-selector-container' }).css({ 'z-index': '1000', 'top': '150px', 'width': '500px', 'position': 'absolute', 'left': '29%', 'background-color': '#E8E8E8' });
		//header
		//close window button
		var videoSelectorHeader = ($('<div/>').css({ 'margin': '0' }).addClass('visBorder'))
			.append(($('<div/>').css({ 'clear': 'both' }).addClass('visHeader visHeaderHover').text(boxcast ? 'BoxCast Broadcast Selector' : 'YouTube Video Selector'))
				.append($('<span/>').attr({ 'id': 'closeVideoSelector', 'title': 'Close' }).css({ 'border-width': '0', 'float': 'right' }).addClass('cw-icon-delete glyphbutton cursor-pointer').off('click').on('click', closeYouTubeVideoEventSelector)));

		videoSelectorWindow.append(videoSelectorHeader);

		//create event button
		videoSelector = $('<div/>').attr({ 'id': 'videoevent-selector' }).css({ 'margin': '0.8em' });
		videoSelector.append($('<hr/>').attr({ 'id': 'hr1' }).css({ 'margin': '1em' }));
		if (youTubeLite) {

			//select video
			var videoList = $('<div/>').text('Paste in YouTube link');
			videoList.append($('<br />'));
			//inpu
			videoList.append($('<input/>').attr({ 'id': 'videoEventId', 'type': 'text', 'placeholder': 'https://youtube.com/watch?v=xxxxxxxxxxx', 'title': 'Paste in YouTube link', 'data-meetingname': meetingName }).css({ 'margin-right': '5px', 'margin-bottom': '3px', 'width': '300px' }));
			videoList.append($('<button/>').attr({ 'id': 'loadMore', 'type': 'button', 'title': 'Load more' }).addClass('button background-color-hover').text('Load More').off('click').on('click', loadMoreVideos));
			videoList.append($('<button/>').attr({ 'id': 'addEventRow', 'type': 'button', 'title': 'Add' }).addClass('button background-color-hover').text('Add').off('click').on('click', addEventRowFromInput));
			videoSelector.append(videoList);
		}
		else {
			var createVideoButton = $('<button/>').attr({ 'id': 'createYouTubeEvent', 'type': 'button', 'title': boxcast ? 'Create a broadcast for this meeting' : 'Create a live event for this meeting' }).addClass('button background-color-hover').text(boxcast ? 'Create New Broadcast' : 'Create New Event').off('click').on('click', function (e) { createYouTubeEvent(e, meetingName); });

			if (boxcast && ((boxcasters && boxcasters.length > 1) || rtmpSources.length > 0))
			{
				videoSelector.append($('<div/>').css('padding-bottom', '5px').append(createVideoButton));
			}
			else
			{
				videoSelector.append($('<div/>').css('text-align', 'center').append(createVideoButton));
			}


			//select video
			var videoList = $('<div/>').text(boxcast ? 'Select Broadcast' : 'Select Video / Current Live Stream');
			videoList.append($('<br />'));
			//combobox
			videoList.append($('<select/>').attr({ 'id': 'videoEventId', 'title': 'Start typing the date of the ' + (boxcast ? 'broadcast' : 'video') + ' then select from the drop down the ' + (boxcast ? 'broadcast' : 'video') + ' you would like associated with this meeting' }).css({ 'margin-right': '5px', 'margin-bottom': '3px', 'height': '25px', 'width': '325px' }).addClass("hidden"));
			videoList.append($('<button/>').attr({ 'id': 'loadMore', 'type': 'button', 'title': 'Load more', 'disabled': 'disabled' }).addClass('button background-color-hover').text('Load More').off('click').on('click', loadMoreVideos));
			videoList.append($('<button/>').attr({ 'id': 'addEventRow', 'type': 'button', 'title': 'Add', 'disabled': 'disabled' }).addClass('button background-color-hover').text('Add').off('click').on('click', (addEventRow)));
			videoList.append(($('<span/>').attr({ 'id': 'videoLoading' })).append($('<span/>').addClass('fa fa-spinner fa-spin')));
			videoSelector.append(videoList);
		}

		videoSelector.append($('<hr/>').attr({ 'id': 'hr2' }).css({ 'margin': '1em' }).addClass('hidden currentlySelectedVideos'));

		videoSelector.append($('<div/>').addClass('hidden currentlySelectedVideos').text('Currently Selected Video(s)'));
		var videoTable = $('<table/>').attr({ 'id': 'currentlySelectedVideosTable' }).addClass('hidden currentlySelectedVideos').css({ 'background-color': 'white', 'width': (boxcast ? '100%': '300px') });
		videoSelector.append(videoTable);

		if (boxcast)
		{
			var boxcasterId = ''
			var youtubeAccountId = '';
			var youtubeeventIds = [];
			if (broadcasts.length > 0)
			{
				for (var i = 0; i < broadcasts.length > 0; i++)
				{
					var broadcastId = broadcasts[i].broadcastId;
					var channelId = broadcasts[i].channelId;
					var youtubeId = broadcasts[i].youtubeId;
					var title = broadcasts[i].title;
					boxcasterId = broadcasts[i].boxcasterId;
					youtubeAccountId = broadcasts[i].youtubeAccountId;
					youtubeeventIds.push(youtubeId);

					videoTable = addBroadcastRowToTable(videoTable, broadcastId, channelId, youtubeId, title);
				}
			}

			//show youtube events not created using boxcaster
			if (events.length > 0)
			{
				for (var i = 0; i < events.length > 0; i++)
				{
					var youtubeId = events[i].eventId;
					var title = events[i].eventTitle;
					if (!youtubeeventIds.includes(youtubeId))
					{
						videoTable = addBroadcastRowToTable(videoTable, '', '', youtubeId, title);
					}	
				}
			}

			if ((boxcasters && boxcasters.length > 0) || (rtmpSources.length > 0))
			{
				var bx = $('<select/>').attr({ 'id': 'boxcastersId' }).css({ 'width': '325px', 'margin-right': '5px', 'height': '25px' });
				for (var i = 0; i < boxcasters.length > 0; i++)
				{
					var id = boxcasters[i].id;
					var name = boxcasters[i].name;	
					bx.append('<option value=' + id + (boxcasterId != '' && id == boxcasterId ? ' selected' : '') + '>' + name + '</option>');
				}
				for (var i = 0; i < rtmpSources.length > 0; i++) {
					var id = rtmpSources[i].id;
					var name = rtmpSources[i].name;
					bx.append('<option value=' + id + (boxcasterId != '' && id == boxcasterId ? ' selected' : '') + '>' + name + '</option>');
				}

				if ((boxcasters.length + rtmpSources.length) == 1)
				{
					bx.addClass('hidden');
					createVideoButton.before(bx);
				}
				else
				{
					createVideoButton.before($('<span/>').text('Source'));
					createVideoButton.before($('<br/>'));
					createVideoButton.before(bx);
				}
			}

			if (youtubeAccounts && youtubeAccounts.length > 0)
			{
				var ac = $('<select/>').attr({ 'id': 'youtubeAccounts' }).css({ 'width': '300px' }).addClass('hidden');
				for (var i = 0; i < youtubeAccounts.length > 0; i++)
				{
					var id = youtubeAccounts[i].id;
					var name = youtubeAccounts[i].name;	
					ac.append('<option value=' + id + (youtubeAccountId != '' && id == youtubeAccountId ? ' selected' : '') + '>' + name + '</option>');
				}
				videoSelectorWindow.append(ac);
			}
		}
		else
		{
			//videos list
		if (events.length > 0) {
			for (var i = 0; i < events.length > 0; i++) {
					var eventId = events[i].eventId;
					var eventTitle = events[i].eventTitle;

					videoTable = addEventRowToTable(videoTable, eventId, eventTitle);
				}
			}
		}

		//start at first time stamp
		//save button
		//remove button
		videoSelector.append($('<hr/>').attr({ 'id': 'hr3' }).css({ 'margin': '1em' }));

		var saveButton = $('<span/>').css({ 'padding-left': '15px' });
		saveButton.append($('<input/>').attr({ 'id': 'startAtFirstTimestamp', 'type': 'checkbox' }).prop('checked', startAtFirstTimestamp).off('click').on('click', function () { enableSaveButton(); }));
		saveButton.append($('<label/>').attr({ 'for': 'startAtFirstTimestamp' }).text('Start At First Timestamp?'));

		saveButton.append(($('<span/>').css({ 'padding-left': '20px' })).append($('<button/>').attr({ 'id': 'saveYouTubeEvents', 'type': 'button', 'disabled': 'disabled', 'title': 'Connect the selected ' + (boxcast ? 'broadcast(s)' : 'video(s)') + ' with this meeting' }).addClass('button button-wide background-color-hover').text('Save').off('click').on('click', saveYouTubeEvents)));
		//saveButton.append($('<input/>').attr({ 'id': 'removeYouTubeVideoEventId', 'type': 'button', 'value': 'Remove', 'title': 'Remove the connected video from this meeting' }).css({ 'margin-left': '2px' }).addClass('button background-color-hover').off('click').on('click', removeYouTubeVideoEventId));

		videoSelector.append($('<div/>').append(saveButton));


		videoSelectorWindow.append(videoSelector);
		$('body').prepend(videoSelectorWindow);

		$('#videoevent-selector-container').draggable({
			handle: 'div.visHeader',
			containment: 'body',
			scroll: false
		});
		if (boxcast)
		{
			localization.meetingDateInThePast = localization.meetingDateInThePast.replace("video", "broadcast").replace("live event", "broadcast");
			localization.meetingStartTimeDoesNotExists = localization.meetingStartTimeDoesNotExists.replace("live event", "broadcast");
			localization.meetingNameToLong = localization.meetingNameToLong.replace("live event", "broadcast");
		}
		if (!youTubeLite) {
			var searchVideoMsg = $('<div id="searchLiveMsg" class="hidden">');
			searchVideoMsg.append(CivicWeb.Common.Notification.create('search-live-msg', CivicWeb.Common.Notification.types.warning, 'Searching for the YouTube live stream may take a few minutes.', false, false));
			$('#hr3').after(searchVideoMsg);

			if (boxcast && boxcasters.length == 0 && rtmpSources.length == 0)
			{
				$('#hr1').after(CivicWeb.Common.Notification.create('create-event-msg', CivicWeb.Common.Notification.types.warning, "Please validate the BoxCast credentials before creating a broadcast", false, false));
				$('#createYouTubeEvent').attr({ 'disabled': 'disabled' });
			}
			else if (meetingDateInThePast)
			{
				$('#hr1').after(CivicWeb.Common.Notification.create('create-event-msg', CivicWeb.Common.Notification.types.warning, localization.meetingDateInThePast, false, false));
				$('#createYouTubeEvent').attr({ 'disabled': 'disabled' });
			}
			else if (!meetingStartTimeExists) {
				var meetingStartTimeDoesNotExist = window.location.href.indexOf('MeetingDetail.aspx') > -1 ? localization.meetingStartTimeDoesNotExists + '.' : localization.meetingStartTimeDoesNotExists + ' from the <a href="/eaengine/MeetingDetail.aspx?id=' + meetingId + '">Overview Page.</a>';


				$('#hr1').after(CivicWeb.Common.Notification.create('create-event-msg', CivicWeb.Common.Notification.types.warning, meetingStartTimeDoesNotExist, false, false));
				$('#createYouTubeEvent').attr({ 'disabled': 'disabled', 'title': localization.meetingStartTimeDoesNotExists });
			}
			else if (meetingName.length > 100) {
				$('#hr1').after(CivicWeb.Common.Notification.create('create-event-msg', CivicWeb.Common.Notification.types.warning, localization.meetingNameToLong.replace("{0}", meetingName.length), false, false));
				$('#createYouTubeEvent').attr({ 'disabled': 'disabled' });
			}

			populateYouTubeVideoDropDown(true, boxcast);
		}

		if (events.length > 0 || broadcasts && broadcasts.length > 0)
		{
			$('.currentlySelectedVideos').removeClass('hidden');
		}

		e.preventDefault();
	};

	var addEventRowFromInput = function (e) {
		var youTubeLink = validateYouTubeUrl($('#videoEventId').val());
		if (youTubeLink.length > 0) {
			var eventId = youTubeLink;
			var eventTitle = $('#videoEventId').attr('data-meetingname');

			var videoTable = $('#currentlySelectedVideosTable');

			if (eventId != '0' && eventId.length > 0 && videoTable.find('a[eventId="' + eventId + '"]').length == 0 && videoTable.children().length < 9) {
				videoTable = addEventRowToTable(videoTable, eventId, eventTitle);
				nameVideoParts(videoTable);
				$('.currentlySelectedVideos').removeClass('hidden');
				$('#videoEventId').val('');
				enableSaveButton();
			}
			$('#invalid-youtube-msg').remove();
		}
		else {
			$('#hr1').after(CivicWeb.Common.Notification.create('invalid-youtube-msg', CivicWeb.Common.Notification.types.warning, "Please enter a valid YouTube broadcast link", false, false));
		}

		e.preventDefault();
	}

	function validateYouTubeUrl(url) {
		if (url != undefined || url != '') {
			var regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=|\?v=)([^#\&\?]*).*/;
			var match = url.match(regExp);
			if (match && match[2].length == 11) {
				return match[2];
			}
			else {
				return '';
			}
		}
	}

	var removeEventRow = function (e) {
		$(this).closest('tr').remove();

		if ($('.selectedEvent').length > 0) {
			nameVideoParts($('#currentlySelectedVideosTable'));
			$('.currentlySelectedVideos').removeClass('hidden');
		}
		else {
			$('.currentlySelectedVideos').addClass('hidden');
		}

		enableSaveButton();

		e.preventDefault();
	};

	var addEventRow = function (e) {
		var eventId = $('#videoEventId option:selected').val();
		var eventTitle = $("#videoEventId option:selected").text();//.replace('**Live** ', '').replace(' (Video)', '').replace(' (Event)', '');

		var videoTable = $('#currentlySelectedVideosTable');

		if (eventId != '0' && eventId.length > 0 && videoTable.find('a[eventId="' + eventId + '"]').length == 0 && videoTable.children().length < 9)
		{
			const video = videoObjects.find((obj) => obj.value === eventId);

			if (purchasedBoxcast)
			{
				if (video.type === "boxcast")
				{
					eventTitle = video.label.replace(boxcastText);
					videoTable = addBroadcastRowToTable(videoTable, eventId, '', '', eventTitle);
				}
				else
				{
					eventTitle = video.label.replace(youtubeText);
					videoTable = addBroadcastRowToTable(videoTable, '', '', eventId, eventTitle);
				}
			}
			else
			{
				videoTable = addEventRowToTable(videoTable, eventId, eventTitle);
			}
			
			nameVideoParts(videoTable);
			$('.currentlySelectedVideos').removeClass('hidden');
			enableSaveButton();
		}

		e.preventDefault();
	};

	var addEventRowToTable = function (videoTable, eventId, eventTitle)
	{
		var videoRow = $('<tr/>');
		var videoCell = ($('<td/>')).append($('<a/>').attr({ 'href': 'https://www.youtube.com/watch?v=' + (eventId.length > 0 ? eventId : '#'), 'target': '_blank', 'eventId': eventId, 'eventTitle': eventTitle }).addClass('selectedEvent subMenuText').text(eventTitle));
		var buttonCell = ($('<td/>').css({ 'text-align': 'right' })).append(($('<span/>').attr({ 'role': 'button', 'title': 'Remove' }).css({ 'color': '#d20000', 'padding-left': '2em' }).addClass('glyphbutton text-negative button-spacing').off('click').on('click', removeEventRow)).append($('<span/>').addClass('fas fa-times')));

		videoRow.append(videoCell);
		videoRow.append(buttonCell);

		videoTable.append(videoRow);

		return videoTable;
	};

	var addBroadcastRowToTable = function(videoTable, broadcastId, channelId, youtubeId, title)
	{
		var videoRow = $('<tr/>');
		var textCell = ($('<td/>')).attr({ 'eventId': youtubeId, 'broadcastId': broadcastId, 'channelId': channelId, 'eventTitle': title }).addClass('selectedEvent subMenuText').text(title);
		var broadcastCell = ($('<td/>')).append($('<a/>').attr({ 'href': 'https://dashboard.boxcast.com/#/events/' + (broadcastId.length > 0 ? broadcastId : '#'), 'target': '_blank', 'eventId': broadcastId, 'eventTitle': title }).text(broadcastId.length > 0 ? "Broadcast" : ""));
		var youtubeCell = ($('<td/>')).append($('<a/>').attr({ 'href': 'https://www.youtube.com/watch?v=' + (youtubeId.length > 0 ? youtubeId : '#'), 'target': '_blank', 'eventId': youtubeId, 'eventTitle': title }).text(youtubeId.length > 0 ? "YouTube" : ""));
		var buttonCell = ($('<td/>').css({ 'text-align': 'right' })).append(($('<span/>').attr({ 'role': 'button', 'title': 'Remove' }).css({ 'color': '#d20000', 'padding-left': '2em' }).addClass('glyphbutton text-negative button-spacing').off('click').on('click', removeEventRow)).append($('<span/>').addClass('fas fa-times')));

		videoRow.append(textCell);
		videoRow.append(broadcastCell);
		videoRow.append(youtubeCell);
		videoRow.append(buttonCell);

		videoTable.append(videoRow);

		return videoTable;
	};

	var nameVideoParts = function (videoTable) {
		var partsText = [' (Part 1)', ' (Part 2)', ' (Part 3)', ' (Part 4)', ' (Part 5)', ' (Part 6)', ' (Part 7)', ' (Part 8)', ' (Part 9)']

		if (videoTable.children().length < 10) {
			var selectedVideoLinks = videoTable.find('.subMenuText');
			for (var i = 0; i < selectedVideoLinks.length; i++) {
				var videoName = $(selectedVideoLinks[i]).text();
				var partName = videoName.substring(videoName.length - partsText[0].length, videoName.length);
				if (partsText.indexOf(partName) > -1) {
					videoName = videoName.substring(0, videoName.length - partsText[0].length);
				}

				$(selectedVideoLinks[i]).text(videoName + (selectedVideoLinks.length > 1 ? partsText[i] : ''));
			}
		}

	};

	var enableSaveButton = function () {
		var saveButton = $('#saveYouTubeEvents');
		saveButton.parent().addClass('wizard');
		saveButton.attr('disabled', false).css({ 'font-weight': 'bold' }).addClass('current');
	};

	var loadMoreVideos = function () {
		$('#addEventRow').attr({ 'disabled': 'disabled' });
		$('#loadMore').attr({ 'disabled': 'disabled' });
		$('#videoLoading').removeClass('hidden');

		populateYouTubeVideoDropDown(false);
	};

	this.populateYouTubeVideoDropDown = function () {
				populateYouTubeVideoDropDown(false);
		};

	var populateYouTubeVideoDropDown = function (includeEvents, boxcast = false) {
		$.ajax({
			url: '/api/getvideos?nextPageToken=' + nextPageToken,
			contentType: 'application/json', dataType: 'json', async: true, cache: false, type: 'GET',
			success: function (response) {
				videoObjects = response.videos;
				nextPageToken = response.nextPageToken;
				var liveEventId = '';
				var liveEventName = '';
				liveEventExists = false;
				broadcastsChannels = {};

				var s = $('#videoEventId');
				// s.find('option').remove();
				if ($('#videoEventId option[value="0"]')?.length === 0) {
					s.prepend('<option value="0"></option>');
								}

				if (boxcast)
				{
					const boxcastVideos = videoObjects.filter((b) => b.type === "boxcast").sort((a, b) => (a.start < b.start ? 1 : a.start > b.start ? -1 : 0));

					$.each(boxcastVideos, function (key, value)
					{
						if (value.channelId)
						{
							broadcastsChannels[value.value] = value.channelId;
						}

						if ($('#videoEventId option[value="' + value.value + '"]')?.length === 0) {
							s.append('<option value=' + value.value + '>' + boxcastText + value.label + '</option>');
						}
					});

				}
				const youtubeVideos = (boxcast ? videoObjects.filter((b) => b.type === "youtube") : videoObjects).sort((a, b) => (a.start < b.start ? 1 : a.start > b.start ? -1 : 0));
				
				if (youtubeVideos != null && youtubeVideos.length > 0 && nextPageToken != null && nextPageToken.length > 0) {
					$('#loadMore').removeClass('hidden');
					$('#loadMore').removeAttr('disabled');
				} else {
					$('#loadMore').addClass('hidden');
				}

				$.each(youtubeVideos, function (key, value) {
					if (value.channelId)
					{
						broadcastsChannels[value.value] = value.channelId;
					}

					if (value.liveBroadcast == 'live') {
						liveEventId = value.value;
						liveEventName = value.label;
						liveEventExists = true;
					}
					else if (value.liveBroadcast == 'upcoming') {
						if (includeEvents) {
							if ($('#videoEventId option[value=' + value.value + ']')?.length === 0) {
								s.append('<option value="' + value.value + '">' + (boxcast ? youtubeText : "") + value.label + ' (Event)</option>');    
							}
						}
					}
					else {
						if ($('#videoEventId option[value="' + value.value + '"]')?.length === 0) {
							s.append('<option value=' + value.value + '>' + (boxcast ? youtubeText : "") + value.label + '</option>');
						}
					}
				});

				if (liveEventId.length > 0) {
					if ($('#videoEventId option[value="' + liveEventId + '"]')?.length === 0) {
						s.prepend('<option value=' + liveEventId + ' selected>**Live** ' + liveEventName + '</option>');
					}
					
					videoSelected = true;
				}

				$('#addEventRow').removeAttr('disabled');
				$('#videoLoading').addClass('hidden');

				if (response.length < 800)
				{
					createYouTubeVideoCombobox();
				}
				else
				{
					$('#videoEventId').attr({'title': 'Select from the drop down the ' + (boxcast ? 'broadcast' : 'video') + ' you would like associated with this meeting' }).removeClass("hidden");
				}

				if (liveEventExists)
				{
					$('#videoSelectorInput').val('**Live** ' + liveEventName);
				}

			},
			error: function () {
				//return '';
			}
		});
	};

	var createYouTubeVideoCombobox = function () {
		$.widget("custom.combobox", {
			_create: function () {
				this.wrapper = $("<span>")
					.addClass("custom-combobox")
					.insertAfter(this.element);

				this.element.hide();
				this._createAutocomplete();
				this._createShowAllButton();
			},

			_createAutocomplete: function () {
				var selected = this.element.children(":selected"),
					value = selected.val() ? selected.text() : "";

				this.input = $("<input id='videoSelectorInput'>")
					.appendTo(this.wrapper)
					.val(value)
					.attr("title", "")
					.css({ 'width': '300px', 'max-width': '300px', 'background': 'white', 'height': '24px' })
					.addClass("custom-combobox-input ui-widget ui-widget-content ui-state-default ui-corner-left")
					.autocomplete({
						delay: 0,
						minLength: 0,
						source: $.proxy(this, "_source")
					})
					.tooltip({
						classes: {
							"ui-tooltip": "ui-state-highlight"
						}
					});

				this._on(this.input, {
					autocompleteselect: function (event, ui) {
						ui.item.option.selected = true;
						this._trigger("select", event, {
							item: ui.item.option
						});
					},

					autocompletechange: "_removeIfInvalid"
				});
			},

			_createShowAllButton: function () {
				var input = this.input,
					wasOpen = false;

				$("<a>")
					.attr("tabIndex", -1)
					.attr("title", "Show All Items")
					.css({ 'height': '25px', 'vertical-align': 'top', 'margin-top': '2px', 'margin-right': '5px' })
					.tooltip()
					.appendTo(this.wrapper)
					.button({
						icons: {
							primary: "ui-icon-triangle-1-s"
						},
						text: false
					})
					.removeClass("ui-corner-all")
					.addClass("custom-combobox-toggle ui-corner-right")
					.on("mousedown", function () {
						wasOpen = input.autocomplete("widget").is(":visible");
					})
					.on("click", function () {
						input.trigger("focus");

						// Close if already visible
						if (wasOpen) {
							return;
						}

						// Pass empty string as value to search for, displaying all results
						input.autocomplete("search", "");
					});
			},

			_source: function (request, response) {
				var matcher = new RegExp($.ui.autocomplete.escapeRegex(request.term), "i");
				response(this.element.children("option").map(function () {
					var text = $(this).text();
					if (this.value && (!request.term || matcher.test(text)))
						return {
							label: text,
							value: text,
							option: this
						};
				}));
			},

			_removeIfInvalid: function (event, ui) {

				// Selected an item, nothing to do
				if (ui.item) {
					return;
				}

				// Search for a match (case-insensitive)
				var value = this.input.val(),
					valueLowerCase = value.toLowerCase(),
					valid = false;
				this.element.children("option").each(function () {
					if ($(this).text().toLowerCase() === valueLowerCase) {
						this.selected = valid = true;
						return false;
					}
				});

				// Found a match, nothing to do
				if (valid) {
					return;
				}

				// Remove invalid value
				this.input
					.val("")
					.attr("title", value + " didn't match any item")
					.tooltip("open");
				this.element.val("");
				this._delay(function () {
					this.input.tooltip("close").attr("title", "");
				}, 2500);
				this.input.autocomplete("instance").term = "";
			},

			_destroy: function () {
				this.wrapper.remove();
				this.element.show();
			}
		});

		$("#videoEventId").combobox();

		$('.ui-autocomplete').css({ 'z-index': 14000, 'max-height': '165px', 'overflow': 'auto', 'border': '1px solid transparent' });
	};

	var createYouTubeEvent = function (e, meetingName) {
		var videoTable = $('#currentlySelectedVideosTable');

		if (videoTable.children().length < 9) {
			videoTable = addEventRowToTable(videoTable, '', meetingName);
			nameVideoParts(videoTable);
			$('.currentlySelectedVideos').removeClass('hidden');
			//problem with all events getting the title updated correctly in YouTube
			//var events = $('.selectedEvent');
			//if (events.length == 1)
			//{
			//	$('#createYouTubeEvent').attr('disabled', 'disabled').removeClass('background-color-hover').text('Creating...  ').append($('<span></span>').append($('<span></span>').addClass('fa fa-spinner fa-spin')));
			//	saveYouTubeEvents(e);
			//}
			//else
			//{
			enableSaveButton();
			//}
		}

		e.preventDefault();
	};

	var saveYouTubeEvents = function (e) {
		$('#saveYouTubeEvents').attr('disabled', 'disabled').text('Saving').css({ 'font-weight': 'normal' }).removeClass('current').append($('<span/>').addClass('fa fa-spinner fa-spin').css({ 'float': 'right', 'margin-left': '5px', 'margin-top': '4px' }));
		var eventsObject = [];
		var events = $('.selectedEvent');
		for (var i = 0; i < events.length; i++)
		{
			var eventId = $(events[i]).attr('eventId') != null ? $(events[i]).attr('eventId') : '';
			var broadcastId = $(events[i]).attr('broadcastId') != null ? $(events[i]).attr('broadcastId') : '';
			var channelId = $(events[i]).attr('channelId') ? $(events[i]).attr('channelId') : broadcastsChannels[broadcastId];
			var boxcasterId = $('#boxcastersId option:selected').val();
			var youtubeAccountId = $('#youtubeAccounts option:selected').val();
			var eventTitle = $(events[i]).text();
			var source = '';
			$.ajax({
				url: '/api/getevent/' + meetingId.toString(),
				contentType: 'application/json', dataType: 'json', async: false, cache: false, type: 'GET',
				success: function (result) {
					var data = JSON.parse(result);
					var rtmpSources = data.rtmpSources != null ? data.rtmpSources : [];
					if (rtmpSources.length > 0) {
						for (var i = 0; i < rtmpSources.length > 0; i++) {
							if (rtmpSources[i].id.toString() == boxcasterId.toString()) {
								source = 'rtmp';
							}
						}
					}
				},
				error: function () {
					//return '';
				}
			});

			eventsObject.push({ 'eventId': eventId, 'broadcastId': broadcastId, 'channelId': channelId, 'boxcasterId': boxcasterId, 'eventTitle': eventTitle, 'youtubeAccountId': youtubeAccountId, 'source': source });
		}

		saveVideoEventSettings(eventsObject, $('#startAtFirstTimestamp').prop('checked'));

		if (eventsObject.length > 1) {
			CivicWeb.Common.Instrumentation.recordAction('VMHD: Added multiple events - saveYouTubeEvents', meetingId);
		}

		e.preventDefault();
	};

	var getAdditionalEvents = function () {
		var obj = {};
		obj.MeetingId = meetingId;
		obj.CurrentEvents = youTubeEvents;

		console.log('getAdditionalEvents');

		$.ajax({
			url: '/api/getadditionalevents/' + meetingId.toString(),
			contentType: 'application/json',
			dataType: 'json',
			async: true,
			cache: false,
			type: 'GET',
			success: function (response) {
				var nextNewEvent = addNewEventsAndGetNext(response);
				var nextNewEventId = nextNewEvent != null && nextNewEvent.eventId != null ? nextNewEvent.eventId : '';

				if (window.myPlayer != null && nextNewEventId.length > 0) {
					updateEventDropDown();
					window.myPlayer.loadVideoById(nextNewEventId, 0, "large");
				}
				else if (window.myPlayer != null && window.myPlayer.getPlayerState() == YT.PlayerState.BUFFERING) {
					//if still buffering
					//keep checking every 10 seconds
					setTimeout(function () { getAdditionalEvents(); }, 10000);
				}
			},
			error: function () {
				//return '';
			}
		});
	};

	var eventIsYouTubeVideo = function (videoId)
	{
		const regex = /[a-zA-Z0-9_-]{11}/g;
		return videoId && videoId.length == 11 && videoId.search(regex) > -1;
	};

	var loadBoxCastVideo = function (containerId, broadcastChannelId)
	{
		var p = $('#videoDiv').detach();
		var timeStampVideoDiv = p.find("#timeStampVideoDiv");
		timeStampVideoDiv.css('height', '100%');
		timeStampVideoDiv.append($("<div id =\"boxcast-widget-" + broadcastChannelId + "\"></div><script type=\"text/javascript\" charset=\"utf-8\">(function(d, s, c, o) {var js = d.createElement(s), fjs = d.getElementsByTagName(s)[0];var h = (('https:' == document.location.protocol) ? 'https:' : 'http:');js.src = h + '//js.boxcast.com/v3.min.js';js.onload = function() { boxcast.noConflict()('#boxcast-widget-'+c).loadChannel(c, o); };js.charset = 'utf-8';fjs.parentNode.insertBefore(js, fjs);}(document, 'script', '" + broadcastChannelId + "', {\"showTitle\":0,\"showDescription\":0,\"showHighlights\":0,\"showRelated\":false,\"defaultVideo\":\"next\",\"market\":\"partner\",\"showCountdown\":false,\"alwaysShowMediaControl\":1,\"showDocuments\":false,\"showIndex\":false,\"showDonations\":false}));</script>"));

		if (attachmentPane)
		{
			p.css('height', '100%');
			attachmentPane.prepend(p);
			setTimeout(function () { resizeVideoDiv(null); setVideoSize(); }, 100);
		}
		else if (documentBody)
		{
			documentBody.prepend(p);
			setTimeout(function () { resizeVideoDiv(null); setVideoSize(); }, 100);
		}
	};

	var loadYouTubeVideo = function (containerId) {
		var startAt = 0;

		if (startAtFirstTimestamp && firstTimeStamp < Number.MAX_SAFE_INTEGER) {
			startAt = firstTimeStamp;
		}
		if (window.location.href.indexOf('timestamp') > 0) {
			startAt = queryValues.timestamp;
		}

		var player = {
			playVideo: function (container, videoId) {
				if (typeof (YT) == 'undefined' || typeof (YT.Player) == 'undefined') {
					window.onYouTubePlayerAPIReady = function () {
						player.loadPlayer(container, videoId);
					};

					var script = document.createElement('script');
					script.type = "text/javascript";
					script.src = "//www.youtube.com/player_api";
					$('body').append(script);

				} else {
					player.loadPlayer(container, videoId);
				}
			},
			loadPlayer: function (container, videoId) {
				window.myPlayer = new YT.Player(container, {
					playerVars: {
						modestbranding: 1,
						rel: 0,
						showinfo: 0,
						autoplay: 0,
						start: startAt
					},
					height: videoHeight,
					width: videoWidth,
					videoId: videoId,
					events: {
						'onReady': onPlayerReady,
						'onStateChange': onPlayerStateChange
					}
				});

				p = $('#videoDiv').detach();

				if (attachmentPane) {
					p.css('height', '100%');
					attachmentPane.prepend(p);
					resizeVideoDiv(null);
				}
				else if (documentBody) {
					documentBody.prepend(p);
					resizeVideoDiv(null);
				}
			}
		};
		player.playVideo('timeStampVideoDiv', youTubeEventId);
	};

	var getCurrentUrlQueryValues = function () {
		var vars = [], hash;
		var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
		for (var i = 0; i < hashes.length; i++) {
			hash = hashes[i].split('=');
			vars.push(hash[0]);
			vars[hash[0]] = hash[1];
		}
		return vars;
	};

	var updateEventDropDown = function () {
		if (minutesBuild) {
			$('#multiVideoDropDown').remove();

			var events = CivicWeb.Integration.Video.getEvents();
			var eventDropDown = $('<select/>').attr({ 'id': 'multiVideoDropDown', 'width': (videoWidth - 2) + 'px' }).css({ 'width': (videoWidth - 2) + 'px', 'max-width': (videoWidth - 2) + 'px', 'margin': '0', 'padding': '0' }).change(function () { var currentEventId = $(this).val(); switchEvents(currentEventId); });
			if (events != null && events.length > 1) {
				for (var i = 0; i < events.length; i++) {
					eventDropDown.append($('<option/>').attr({ 'value': events[i].eventId }).css({ 'width': (videoWidth - 2) + 'px', 'max-width': (videoWidth - 2) + 'px' }).text(events[i].eventTitle));
				}
				eventDropDown.val(youTubeEventId);
				$('#timeStampVideoDiv').before(eventDropDown);
			}
		}
	};

	var addNewEventsAndGetNext = function (events) {
		var newEvent = '';
		var existingEventIds = []
		for (var i = 0; i < youTubeEvents.length; i++) {
			existingEventIds.push(youTubeEvents[i].eventId);
		}

		for (var j = 0; j < events.length; j++) {
			if (existingEventIds.indexOf(events[j].eventId) == -1) {
				currentVideo = j;
				youTubeEventId = events[j].eventId
				youTubeEvents = events;

				return events[j];
			}
		}

		return newEvent;
	};

	function onPlayerReady(event) {
		//if (!isIOS) {
		//	event.target.playVideo();
		//}
	};

	function onPlayerStateChange(event) {
		//if we hit any state change clear any search for additional events.
		clearTimeout(searchingForAdditionalEvents);

		//if the video has ended and there is another event then play the next one
		if (event.data == YT.PlayerState.ENDED) {
			if (currentVideo + 1 < youTubeEvents.length) {
				currentVideo = currentVideo + 1;
				youTubeEventId = youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo].eventId != null ? youTubeEvents[currentVideo].eventId : '';

				if (youTubeEventId.length > 0) {
					updateEventDropDown();
					window.myPlayer.loadVideoById(youTubeEventId, 0, "large");
				}
			}
			else {
				getAdditionalEvents();
			}
		}
		else if (event.data == YT.PlayerState.BUFFERING) {
			//BUFFERING may happend anytime during the stream
			//BUFFERING happens when the stream is paused i.e. hour lunch
			//BUFFERING happens when the stream is complete
			searchingForAdditionalEvents = setTimeout(
				function () {
					if (currentVideo + 1 < youTubeEvents.length) {
						currentVideo = currentVideo + 1;
						youTubeEventId = youTubeEvents.length >= currentVideo && youTubeEvents[currentVideo].eventId != null ? youTubeEvents[currentVideo].eventId : '';

						if (youTubeEventId.length > 0) {
							updateEventDropDown();
							window.myPlayer.loadVideoById(youTubeEventId, 0, "large");
						}
					}
					else {
						getAdditionalEvents();
					}

				}, 10000);
		}
	};

	(function () {
		if (manageVideo && meetingId != null && meetingId > 0) {
			setUpViewCreateEventLink(meetingId);
		}

		if (manageVideo && earthChannel) {
			var eventMethod = window.addEventListener ? "addEventListener" : "attachEvent";
			var eventer = window[eventMethod];
			var messageEvent = eventMethod == "attachEvent" ? "onmessage" : "message";

			eventer(messageEvent, function (e) {
				var key = e.message ? "message" : "data";
				var data = e[key];
				if (data.indexOf("ECPlayerTime:") === 0) {
					var secs = data.split(":")[1];
					setVideoTimeStampDataCallback(itemId, secs, true);

				}
			}, false);
		}

		if (audioOnly) {
			$('#timeStampSyncVideo').attr({ 'title': 'Sync timestamps with recorded audio' });
			$('#timeStampVideoButton').attr({ 'title': 'Play the recorded audio' }).find('span').text('Play Audio');
		}

		if (minutesBuild) {
			setUpMinutesToTimeStamp(meetingId);
		}

		queryValues = getCurrentUrlQueryValues();

		isPhone = /android|webos|iphone|ipod|blackberry|iemobile|opera mini/i.test(navigator.userAgent.toLowerCase());
		isIOS = /ipad|iphone|ipod/i.test(navigator.userAgent.toLowerCase());

	})();
}

//Objects
CivicWeb.Integration.Video = {
	//Properties
	instance: null,


	createInstance: function (args) {
		if (this.instance) {
			delete this.instance;
		}
		this.instance = new CivicWeb.Integration.VideoClass(args);
	},

	getPublishedVideoUrl: function (id, f) {
		return this.instance.getPublishedVideoUrl(id, f);
	},

	addTimestampsAndVideoToMeetingDocument: function (meetingId, body, splitscreen) {
		return this.instance.addTimestampsAndVideoToMeetingDocument(meetingId, body, splitscreen);
	},

	moveVideoToAgendaFrame: function (moveBackToAttachmentFrame, i) {
		return this.instance.moveVideoToAgendaFrame(moveBackToAttachmentFrame, (i ? i : 1));
	},

	moveVideoToAttachmentFrame: function () {
		return this.instance.moveVideoToAttachmentFrame();
	},

	addVideoButtonToPortal: function (meetingId, documentId, buttonClient) {
		return this.instance.addVideoButtonToPortal(meetingId, documentId, buttonClient);
	},

	getEvents: function () {
		return this.instance.getEvents();
	},

	getCurrentEvent: function () {
		return this.instance.getCurrentEvent();
	},

	getVideoTime: function (iframe, itemId, callback) {
		return this.instance.getVideoTime(iframe, itemId, callback);
	},

	getSyncMode: function () {
		return this.instance.getSyncMode();
	},

	isAudioOnly: function () {
		return this.instance.isAudioOnly();
	},

	isLive: function () {
		return this.instance.isLive();
	},

	toggleTimeStampSyncMode: function () {
		return this.instance.toggleTimeStampSyncMode();
	},

	hideVideo: function (e) {
		return this.instance.hideVideo(e);
	},

	convertSecondsToTimeString: function (secs, hyphens, itemId) {
		return this.instance.convertSecondsToTimeString(secs, hyphens, itemId);
	},

	resizeVideo: function () {
		return this.instance.resizeVideo();
	},

	gotoMinutesVideoTimeStamp: function (e) {
		return this.instance.gotoMinutesVideoTimeStamp(e);
	},

	showPdfQuickViewVideoLink: function (meetingId, documentId) {
		return this.instance.showPdfQuickViewVideoLink(meetingId, documentId);
	},

	populateYouTubeVideoDropDown: function () {
				return this.instance.populateYouTubeVideoDropDown();
		},

	events: {
	}
};
;
