		var ARCHIVE_GROUPS = [];
		var pageNum = 0;
		var POP_EVENT_WIN_HANDLE = null;

			var CDSECI = null;
			var A11Y_STATUS_ID = 'cdsArchiveA11yStatus';
		
	  	/*
			http://colintoh.com/blog/display-table-anti-hero
			*/

			/*

			*/
			function ensureA11yStatusRegion()
			{
				if($('#' + A11Y_STATUS_ID).length > 0)
				{
					return;
				}

					$('body').prepend('<div id="' + A11Y_STATUS_ID + '" class="cdsArchiveVisuallyHidden" aria-live="polite" aria-atomic="true"></div>');
			}

			/*

			*/
				function announceStatus(message)
				{
					if(!message)
						return;

				ensureA11yStatusRegion();
					$('#' + A11Y_STATUS_ID).text(message);
				}

				/*

				*/
				function escapeArchiveHTML(value)
				{
					return String(value || '')
						.replace(/&/g, '&amp;')
						.replace(/</g, '&lt;')
						.replace(/>/g, '&gt;')
						.replace(/"/g, '&quot;')
						.replace(/'/g, '&#39;');
				}

				/*

				*/
				function getArchiveGroupResultColSpan(agID)
				{
					if(isArchiveGroupMediaDisplay(agID)){
						return 6;
					}
					else if(isArchiveGroupCalendarDisplay(agID)){
						return 3;
					}

					return 2;
				}

				/*

				*/
				function isArchiveGroupCalendarDisplay(agID)
				{
					return (ARCHIVE_GROUPS[agID].DisplayTypeID == 1 || ARCHIVE_GROUPS[agID].DisplayTypeID == 4);
				}

				/*

				*/
				function isArchiveGroupMediaDisplay(agID)
				{
					return (ARCHIVE_GROUPS[agID].DisplayTypeID == 3 || ARCHIVE_GROUPS[agID].DisplayTypeID == 4);
				}

				/*

				*/
				function getArchiveAttachmentName(attachment)
				{
					if(!attachment){
						return '';
					}

					var attachmentName = '';
					if(attachment.MediaNickName && attachment.MediaNickName != ''){
						attachmentName = attachment.MediaNickName;
					}
					else{
						attachmentName = (attachment.MediaFileName ? attachment.MediaFileName : '');
					}

					try{
						attachmentName = decodeURIComponent(attachmentName);
					}
					catch(e){
						// Keep the raw attachment name if it is not URI-encoded cleanly.
					}

					return attachmentName;
				}

				/*

				*/
				function renderArchiveAttachmentIcons(attachments, label)
				{
					if(!attachments || attachments.length < 1){
						return '<span class="cdsArchiveNoAttachment" aria-label="No ' + escapeArchiveHTML(label) + ' attachments">--</span>';
					}

					var output = '';
					for(var i=0;i<attachments.length;i++){
						var attName = getArchiveAttachmentName(attachments[i]);
						var safeName = escapeArchiveHTML(attName);
						var attPath = '';

						if(attachments[i].MediaFileLocation && attachments[i].MediaFileName){
							attPath = '/ATT/' + CUSTOMER_ACCESS_ID + '/' + attachments[i].MediaFileLocation + '/' + attachments[i].MediaFileName;
						}

						if(attPath != ''){
							output += '<a class="cdsArchiveAttachmentIcon" href="' + escapeArchiveHTML(attPath) + '" target="_blank" rel="noopener" title="' + safeName + '" aria-label="' + escapeArchiveHTML(label) + ' attachment: ' + safeName + '"><span class="glyphicon glyphicon-file" aria-hidden="true"></span></a>';
						}
						else{
							output += '<span class="cdsArchiveAttachmentIcon" title="' + safeName + '" aria-label="' + escapeArchiveHTML(label) + ' attachment: ' + safeName + '"><span class="glyphicon glyphicon-file" aria-hidden="true"></span></span>';
						}
					}

					return output;
				}

			/*

			*/
		function addTab(archiveGroup)
		{
			var idx = archiveGroup.CustomerArchiveGroupID;
			var tabName  = archiveGroup.GroupName;
			
			ARCHIVE_GROUPS[idx] = archiveGroup;

			  var activeTabID = 0;
			  if(typeof(window['CUSTOMERARCHIVE_TAB_DEFAULT_SELECTED_ID']) != 'undefined')  activeTabID = parseInt(window['CUSTOMERARCHIVE_TAB_DEFAULT_SELECTED_ID']);		

			  var isActive = (pageNum === activeTabID);
			  $('#ulTabControl').append('<li role="presentation"' + (isActive ? ' class="active"' : '') + '><a id="tabHandle_' + idx + '" href="#archiveGroupPage_' + idx + '" role="tab" aria-controls="archiveGroupPage_' + idx + '" aria-selected="' + (isActive ? 'true' : 'false') + '" data-toggle="tab">' + tabName + '</a></li>');
			  $('#divTabContent').append('<div class="tab-pane' + (isActive ? ' active' : '') + '" id="archiveGroupPage_' + idx + '" role="tabpanel" aria-labelledby="tabHandle_' + idx + '"></div>');
			  $('#page' + pageNum).tab('show');
			  pageNum++;
			}

		/*

		*/
		function getAccordionExpandClass(pageNum, idx){
			if(window['CUSTOMERARCHIVE_IS_ACCORDION_COLLAPSED'] == true){
				return '';
			}
			else{
				if(typeof(window['CUSTOMERARCHIVE_ACCORDION_DEFAULT_EXPANDED_ID']) != 'undefined'){
					var accordionExpandedID = window['CUSTOMERARCHIVE_ACCORDION_DEFAULT_EXPANDED_ID'];
					return (accordionExpandedID === idx ? ' in' : '');	
				}
				else{
					return (pageNum === 0 ? ' in' : '');
				}
			}
		}

		/*

		*/
			function addAccordion(archiveGroup)
			{
				var idx = archiveGroup.CustomerArchiveGroupID;
				var accordionName  = archiveGroup.GroupName;
				var isExpanded = (getAccordionExpandClass(pageNum, idx).indexOf('in') > -1);
				
				ARCHIVE_GROUPS[idx] = archiveGroup;

	    		var toWrite  = '<div class="panel panel-default">';
	    	    toWrite += '    <div class="panel-heading cdsAccordionHandle" role="tab" id="heading_' + idx + '">';
	    	    toWrite += '        <h4 class="panel-title"><button type="button" class="btn btn-link cdsAccordionButton" style="color:inherit;" data-toggle="collapse" data-parent="#divAccordionControl" data-target="#collapse_' + idx + '" aria-expanded="' + (isExpanded ? 'true' : 'false') + '" aria-controls="collapse_' + idx + '">' + accordionName + '</button></h4>';
	    	    toWrite += '    </div>';
	    	    toWrite += '    <div id="collapse_' + idx + '" class="panel-collapse collapse ' + getAccordionExpandClass(pageNum, idx) + '" role="tabpanel" aria-labelledby="heading_' + idx + '">';
	    	    toWrite += '        <div class="panel-body" id="archiveGroupPage_' + idx + '"></div>';
    	    toWrite += '    </div>';
    	    toWrite += '</div>';

    		$('#divAccordionControl').append(toWrite);
    		pageNum++;

			// var toWrite = '';
			// toWrite += '<div class="panel-group" id="accordionArchives" role="tablist">';
			
			// for(var i=0;i<data.ArchiveGroups.length;i++)
			// {
			// 	var groupID = data.ArchiveGroups[i].CustomerArchiveGroupID;

			// 	toWrite += '    <div class="panel panel-default">'
			// 	toWrite += '        <div class="panel-heading"><h4 class="panel-title"><a data-toggle="collapse" data-parent="#accordion" href="#accordion_' + groupID + '">' + data.ArchiveGroups[i].GroupName + '</a></h4></div>';
			// 	toWrite += '        <div id="accordion_' + groupID + '" class="cdsArchiveGroup panel-collapse collapse"><div class="panel-body">';
			// 	if(data.ArchiveGroups[i].DisplayTypeID == 1) //1 == calendar, 2 == list
			// 	{
			// 		toWrite += '<div style="display:table-cell; vertical-align:top; padding-right:12px;">' + generateCalendar(data.ArchiveGroups[i]) + '</div>';
			// 		toWrite += '<div id="divEvents_' + groupID + '" class="cdsEvents">' + '<div style="text-align:center;"><br/><br/><h4>loading...</h4></div>' + '</div>';
			// 	}
			// 	toWrite += '        </div></div>';
			// 	toWrite += '    </div>'; //panel
			// }
			// toWrite += '</div>'; //panel group

		}



		/*
		
		*/
		function populateArchiveContainer(callback)
		{
	  	var url = PROTOCOL + '//' + HOST + '/' + CUSTOMER_ACCESS_ID + '/archive/' + ARCHIVE_ID;
	  	//console.log("populateArchiveContainer - URL:", url);
			CDSTools.getJSON(url, function(err, data)
			{	
				//console.log(err, data);
				//console.dir(data);
				if(!data || !data.Archive || !data.ArchiveGroups)
				{				
					if(document.documentMode){
						$('#cdsContent').html("<h2>Oops! Your browser is preventing you from seeing this content.</h2><h4>Perhaps try another browser, or remove this site from your browser's compatibility mode settings.</h4><p><strong>Detail:</strong> Rendered in Internet Explorer " + document.documentMode + " compatibility mode.</p>");
					}
					else{
						$('#cdsContent').html("<h2>There was no archive found.</h2>");
					}
					callback();
				}
				else
				{
						if(data.Archive.DisplayTypeID == 1){ //1 == accordion

							$('#cdsContent').html('<div id="divAccordionControl" class="panel-group" role="tablist"></div>');
						
						for(var i=0;i<data.ArchiveGroups.length;i++)
						{
							addAccordion(data.ArchiveGroups[i]);
							//set up cal, list, whatever...
							populateArchiveGroupContainer(data.ArchiveGroups[i].CustomerArchiveGroupID);

							$('#cdsPageTitle').html(data.Archive.ArchiveTitle);
						}
						}
						else{ //2 == tabs

							$('#cdsContent').html('<ul id="ulTabControl" class="nav nav-tabs" role="tablist"></ul><div id="divTabContent" class="tab-content"></div>');

							for(var i=0;i<data.ArchiveGroups.length;i++)
							{
							addTab(data.ArchiveGroups[i]);
							//set up cal, list, whatever...
							populateArchiveGroupContainer(data.ArchiveGroups[i].CustomerArchiveGroupID);

							$('#cdsPageTitle').html(data.Archive.ArchiveTitle);
						}
					}

					callback(data.Archive, (data.CDSECI ? data.CDSECI : null));
				}

				
				//$('meta[name=description]').attr('content', 
			});
		}

		/*
		
		*/
		function createCalendar(archiveGroup)
		{
			var agID = archiveGroup.CustomerArchiveGroupID;
			var groupNameA11y = (archiveGroup.GroupName ? archiveGroup.GroupName : 'archive group').replace(/"/g, '&quot;');

			var nowMonth = (new Date().getMonth())+1;
			var nowYear = new Date().getFullYear();
			var startYear = 2015;
			var endYear = END_YEAR;

			if(typeof(PRESELECTED_MONTH) != 'undefined' && PRESELECTED_MONTH != null)
				nowMonth = PRESELECTED_MONTH;
			if(typeof(PRESELECTED_YEAR) != 'undefined' && PRESELECTED_YEAR != null)
				nowYear = PRESELECTED_YEAR;
			if(typeof(START_YEAR) != 'undefined' && START_YEAR != null)
				startYear = START_YEAR;

			var output = "";

			output += '<table id="tblCal_' + agID + '" class="cdsArchiveGroupCalChooser" style="margin: 10px;">';
			output += '  <thead>'
			output += '  <tr>';
			output += '    <td colspan="3">';
			output += '      <select class="cdsYearSelect" aria-label="Select year for ' + groupNameA11y + '" title="Select year">';
			for(var i=endYear;i>(startYear-1);i--)
			{
				output += '      <option value="' + i + '"' + (i == nowYear ? ' selected="selected"' : '') + '>' + i + '</option>';
			}
			output += '      </select>';
			output += '    </td>';
			output += '  </tr>';
			output += '  </thead>';

			output += '  <tbody>';
			output += '    <tr><td class="tblCalMonth_0' + (0 === nowMonth ? ' active' : '') + '" colspan="3"><button type="button" class="cdsCalMonthBtn tblCalMonthBtn_0' + (0 === nowMonth ? ' active' : '') + '" data-month="0">All Months</button></td></tr>';
			var m = 1;
			for(var i=1;i<5;i++)
			{
				output += '  <tr>';
				for(var j=1;j<4;j++)
				{
					output += '    <td class="tblCalMonth_' + m + (m === nowMonth ? ' active' : '') + '"><button type="button" class="cdsCalMonthBtn tblCalMonthBtn_' + m + (m === nowMonth ? ' active' : '') + '" data-month="' + m + '">' + DateTools.MONTH_NAMES_SHORT[(m-1)] + '</button></td>';

					++m;
				}
				output += '  </tr>';
			}
			output += '  </tbody>';
			output += '</table>'

			return output;
		}

		/*
		
		*/
			function populateArchiveGroupContainer(agID)
			{
			//$('#archiveGroupPage_' + agID).html('<h4 style="text-align: center; margin-top: 40px;">Fetching...</h4>');
			$('#archiveGroupPage_' + agID).html('');			
				if(isArchiveGroupCalendarDisplay(agID))	{ //1 is CAL, 2 is LIST, 4 is CALENDAR WITH MEDIA
						$('#archiveGroupPage_' + agID).append('<div style="width:100%; display:table;"><div id="divCal_' + agID + '" class="divCalContainer"></div><div class="divCalEventContainer"><div id="divEvents_' + agID + '" class="divCalEvents"></div></div></div>');
						if(isArchiveGroupMediaDisplay(agID)){
							$('#divEvents_' + agID).append('<table id="tbl_' + agID + '" class="table table-condensed table-striped cdsEventTable"><thead><tr><th class="tdEventActions">Action</th><th class="tdEventDateTime">Date</th><th class="tdEventTitle">Event title</th><th class="tdEventAttachment cdsArchiveAgendaAttachmentColumn">Agenda Attachments</th><th class="tdEventAttachment cdsArchiveMinutesAttachmentColumn">Minutes Attachments</th><th class="cdsArchiveLaunchPlayerColumn">Player</th></tr></thead><tbody><tr><td colspan="6">loading...</td></tr></tbody></table>');
						}
						else{
							$('#divEvents_' + agID).append('<table id="tbl_' + agID + '" class="table table-condensed table-striped cdsEventTable"><thead><tr><th class="tdEventActions">Action</th><th class="tdEventDateTime">Date</th><th class="tdEventTitle">Event title</th></tr></thead><tbody><tr><td colspan="3">loading...</td></tr></tbody></table>');
						}

					var cal = createCalendar(ARCHIVE_GROUPS[agID]);

					$('#divCal_' + agID).html(cal);
					}
					else if(ARCHIVE_GROUPS[agID].DisplayTypeID == 3) {
							$('#archiveGroupPage_' + agID).append('<div id="divEvents_' + agID + '" class="divCalEvents"><table id="tbl_' + agID + '" class="table table-condensed table-striped cdsEventTable"><thead><tr><th class="tdEventActions">Action</th><th class="tdEventDateTime">Date</th><th class="tdEventTitle">Event title</th><th class="tdEventAttachment cdsArchiveAgendaAttachmentColumn">Agenda Attachments</th><th class="tdEventAttachment cdsArchiveMinutesAttachmentColumn">Minutes Attachments</th><th class="cdsArchiveLaunchPlayerColumn">Player</th></tr></thead><tbody><tr><td colspan="6">loading...</td></tr></tbody></table></div>');
						}
				else {
						$('#archiveGroupPage_' + agID).append('<div id="divEvents_' + agID + '" class="divCalEvents"><table id="tbl_' + agID + '" class="table table-condensed table-striped cdsEventTable"><thead><tr><th class="tdEventActions">Action</th><th class="tdEventTitle">Event title</th></tr></thead><tbody><tr><td colspan="2">loading...</td></tr></tbody></table></div>');
					}
				}

		/*

		*/
		function getCurrentCalendarDateTimes(agID)
		{
			//console.log("getCurrentCalendarDateTimes for agID:" + agID);
			//console.dir($('#tblCal_' + agID + ' td.active'));
			var output = [];

			var year = $('#tblCal_' + agID + ' td select.cdsYearSelect').val();
				var activeMonthBtn = $('#tblCal_' + agID + ' .cdsCalMonthBtn.active').first();
				if(activeMonthBtn.length < 1){
					return [year + '-01-01T00:00:00', year + '-12-31T23:59:59'];
				}
				var month = activeMonthBtn.attr('data-month');

			if(month == 0)
			{
				output[0] = year + '-01-01T00:00:00';
				output[1] = year + '-12-31T23:59:59';
			}
			else
			{
				month = (month.length == 1 ? ('0' + month) : month);
				
				output[0] = year + '-' + month + '-01T00:00:00';

				var d = new Date(year, month, 0, 0, 0, 0);

				month = (d.getMonth()+1) + '';
				month = (month.length == 1 ? ('0' + month) : month);
				output[1] = d.getFullYear() + '-' + month + '-' + d.getDate() + 'T23:59:59';
			}
			return output;
		}

		/*
		
		*/
		function getECIDataIfNeeded(agID, callback){
			if(CDSECI && CDSECI.isEnabled){
				//console.log("CSECI.publisherGUID:", CDSECI.publisherGUID);
				//https://view.earthchannel.com/extapi/augga/PublisherEvent_JSGetByTimeFrame/2019-03-05T00:00:00/2019-03-05T23:59:59/false/1
				var eciArchivesCSV = (CDSECI.archiveGroupMappings[agID] ? CDSECI.archiveGroupMappings[agID] : 0);

				if(eciArchivesCSV === 0){
					callback(null, []);
					return;
				}

				var eciURL = '';
				if(isArchiveGroupCalendarDisplay(agID)){
					var dts = getCurrentCalendarDateTimes(agID); //array [start, end]
					eciURL = 'https://view.earthchannel.com/extapi/' + CDSECI.publisherGUID + '/PublisherEvent_JSGetByTimeFrame/' + dts[0] + '/' + dts[1] + '/true/' + eciArchivesCSV;
				}
				else{
					eciURL = 'https://view.earthchannel.com/extapi/' + CDSECI.publisherGUID + '/PublisherEvent_JSGetList/true/' + eciArchivesCSV;
				}

				CDSTools.getJSONQuick(eciURL, function(eciERR, eciData){ //eg, give it 5s to get it...
					if(!eciData || !Array.isArray(eciData)){
						console.error('eciDATA was not array');
						return callback(null, []);
					}

					for(var i=0;i<eciData.length;i++){
						eciData[i].EventSourceType = 'ECI';

						try{
							eciData[i].EventDateTimeLocal = new Date(Date.parse(eciData[i].EventDateTimeUTC));
						}
						catch(ex){
							console.error(ex);
						}

						eciData[i].EventDateTimeUTC = eciData[i].EventDateTimeUTC.replace('T', ' ');

					}

					callback(eciERR, eciData);
				}, false);
			}
			else{
				//console.log("NOT GETTING ECI Data");
				callback(null, []);
			}
		}

		/*
		
		*/
		function populateArchiveGroupEvents(agID, callback)
		{
				if(agID < 0){
					return callback();
				}

				if(!ARCHIVE_GROUPS[agID]){
					console.log("ARCHIVE_GROUPS[" + agID + "] was not found...");
					return callback();
				}

					var resultColSpan = getArchiveGroupResultColSpan(agID);
					$('#tbl_' + agID + ' tbody').html('<tr><td colspan="' + resultColSpan + '" align="center">searching...</td></tr>');
					announceStatus('Loading archive events');

			var url = '';
			//1 is CAL, 2 is LIST
			if(isArchiveGroupCalendarDisplay(agID))
			{
				//TODO: here is where we grab the NEWEST one if we need to...
				/*
				if(IS_TANDEM_CHOOSERS) {
					$('.cdsArchiveGroupCalChooser td.active').removeClass('active');
					$('.tblCalMonth_' + monthID).addClass('active');
				}
				*/

				// if(true){
				// 	url = PROTOCOL + '//' + HOST + '/' + CUSTOMER_ACCESS_ID + '/archiveGroupDate/' + agID + '/LOCAL/' + dts[0] + '/' + dts[1];
				// 	CDSTools.getJSON(url, function(err, data) {

				// 	});
				// }
				// else{

				// }

				var dts = getCurrentCalendarDateTimes(agID); //array [start, end]
				var archiveGroupDateEndpoint = (ARCHIVE_GROUPS[agID].DisplayTypeID == 4 ? 'archiveGroupDateWithMedia' : 'archiveGroupDate');
				                                    //'/[a:caID]/archiveGroupDate/[i:archiveGroupID]/[:dateType]/[:dateTimeStartUTC]/[:dateTimeEndUTC]/?'
			  url = PROTOCOL + '//' + HOST + '/' + CUSTOMER_ACCESS_ID + '/' + archiveGroupDateEndpoint + '/' + agID + '/LOCAL/' + dts[0] + '/' + dts[1];
			}
			else if(ARCHIVE_GROUPS[agID].DisplayTypeID == 3){
				url = PROTOCOL + '//' + HOST + '/' + CUSTOMER_ACCESS_ID + '/archiveGroupListWithMedia/' + agID;
			}
			else
			{
	  		url = PROTOCOL + '//' + HOST + '/' + CUSTOMER_ACCESS_ID + '/archiveGroupList/' + agID;
			}

			//console.log("getting:" + url);
				CDSTools.getJSON(url, function(err, data) {
					//console.log("CDS-DATA:", data);

					getECIDataIfNeeded(agID, function(eciErr, eciData){

						if(!data){
							data = [];
						}

						for(var i=0;i<data.length;i++){
							data[i].EventSourceType = 'CDS';
						}

					if(eciData && eciData.length > 0){

						for(var i=0;i<eciData.length;i++){
							for(var j=0;j<data.length;j++){
								if(eciData[i].EventDateTimeUTC >= data[j].EventDateTimeUTC){
									data.splice(j, 0, eciData[i]);
									eciData[i].IsMoved = true;
									break;
								}
							}
						}

						//then get any remainder...
						for(var i=0;i<eciData.length;i++){
							if(!eciData[i].IsMoved){	
								//console.log("PUSHING - eciData", eciData[i]);
								data.push(eciData[i]);
							}
						}
					}

					//console.log("ECI-DATA:", eciData);
					var output = '';

						if(err)
						{
							output = '<tr><td colspan="' + resultColSpan + '" align="center"><h4>Oops! There was an error getting the results.</h4></td></tr>';
						}
						else if(data && data.length == 0)
						{
							output = '<tr><td colspan="' + resultColSpan + '" align="center">There were no programs found.</td></tr>';
							announceStatus('No programs found');
						}
						else
						{					
							for(var i=0;i<data.length;i++)
							{
								//console.log("data[" + i + "].EventDateTimeLocal=" + data[i].EventDateTimeLocal);
								var dto = DateTools.parseCDSDate(data[i].EventDateTimeLocal);
								var dt = '';
								var isMediaList = isArchiveGroupMediaDisplay(agID);

								if(ARCHIVE_GROUPS[agID].DisplayTypeID == 2){
									dt = '';
								}
							else{
								if(window['CUSTOMER_SHOW_DATE_FN']){
									dt = window['CUSTOMER_SHOW_DATE_FN'](dto);
								}
								else if(window['CUSTOMER_SHOW_DATE_FN_ARCHIVE_GROUP_' + agID]){
									dt = window['CUSTOMER_SHOW_DATE_FN_ARCHIVE_GROUP_' + agID](dto);
								}
								else{
									dt = DateTools.MONTH_NAMES_SHORT[dto.getMonth()] + " " + dto.getDate() + StringTools.nth(dto.getDate());
								}
							}

							//console.log("ARCHIVE_GROUPS[agID]", ARCHIVE_GROUPS[agID]);
							var eventID = 0;
							var eventClassName = '';
							if(data[i].EventSourceType == 'CDS'){
								eventID = data[i].CustomerEventID;
								eventClassName = 'cdsEvent';
							}
								else if(data[i].EventSourceType == 'ECI'){
									eventID = data[i].PublisherEventID;
									eventClassName = 'eciEvent';
								}

									var eventTitle = escapeArchiveHTML(data[i].EventTitle);
									output += '<tr id="trEvent_' + eventID + '" class="' + eventClassName + '" data-source="' + data[i].EventSourceType + '" data-event-id="' + eventID + '">';
									if(dt != '' || isMediaList){
										output += '    <td class="tdEventActions"><button type="button" class="btn btn-default btn-xs cdsEventLaunch" data-source="' + data[i].EventSourceType + '" data-event-id="' + eventID + '" aria-label="Open event: ' + eventTitle + '">Open</button></td><td class="tdEventDateTime" role="button" tabindex="0" aria-label="Open event date and time">' + escapeArchiveHTML(dt) + '</td>';
										output += '    <td class="tdEventTitle" role="button" tabindex="0" aria-label="Open event: ' + eventTitle + '">' + eventTitle + '</td>';
										if(isMediaList){
											output += '    <td class="tdEventAttachment cdsArchiveAgendaAttachmentColumn">' + renderArchiveAttachmentIcons((data[i].Agenda && data[i].Agenda.Attachments ? data[i].Agenda.Attachments : []), 'Agenda') + '</td>';
											output += '    <td class="tdEventAttachment cdsArchiveMinutesAttachmentColumn">' + renderArchiveAttachmentIcons((data[i].Minutes && data[i].Minutes.Attachments ? data[i].Minutes.Attachments : []), 'Minutes') + '</td>';
											output += '    <td class="cdsArchiveLaunchPlayerColumn"><button type="button" class="btn btn-default btn-xs cdsEventLaunch" data-source="' + data[i].EventSourceType + '" data-event-id="' + eventID + '" aria-label="Launch player for event: ' + eventTitle + '">Launch Player</button></td>';
										}
									}
									else{
										output += '    <td class="tdEventActions"><button type="button" class="btn btn-default btn-xs cdsEventLaunch" data-source="' + data[i].EventSourceType + '" data-event-id="' + eventID + '" aria-label="Open event: ' + eventTitle + '">Open</button></td>';
										output += '    <td class="tdEventTitle" role="button" tabindex="0" aria-label="Open event: ' + eventTitle + '">' + eventTitle + '</td>';
									}
									output += '</tr>';
								}
							announceStatus(data.length + ' programs found');
						}

					$('#tbl_' + agID + ' tbody').html(output);

					if(callback)
						callback();
				});
			});
		}

		/*

		*/
			function tabSelect(agID, callback)
			{
				populateArchiveGroupEvents(agID, function()
				{
					if(callback)
						callback();
				});
		}



		/*
	
		*/
		function getIDXFromID(id)
		{
			var output = -1;
			if(id && id.indexOf("_") > -1)
			{
				var ids = id.split('_');
				if(ids.length == 2)
					output = ids[1];
			}
			else
			{
				//console.log("getIDXFromID - not found from:" + id);
			}
			return output;
		}

		/*

		*/
		function popEventWindow(id, url)
		{
			if(POP_EVENT_WIN_HANDLE)
			{
				try
				{
					POP_EVENT_WIN_HANDLE.close();
				}
				catch(ex)
				{
					console.log('popEventWindow ERR:', ex);
				}
			}


			POP_EVENT_WIN_HANDLE = window.open(url, id, 'scrollbars=yes,width=' + POP_WINDOW_DIMS[0] + ',height=' + POP_WINDOW_DIMS[1]);
		}

			/*

			*/
			function launchArchiveEvent(eventID, sourceType)
			{
				if(!eventID)
					return;

				var idx = parseInt(eventID);
				var url = '';
				if(sourceType == 'ECI'){
					url = 'https://view.earthchannel.com/PlayerController.aspx?&PGD=' + CDSECI.publisherGUID + '&eID=' + idx;
				}
				else{
					url = '/' + CUSTOMER_ACCESS_ID + '/event/' + idx;
				}

				popEventWindow('CDSEventWin', url);
				announceStatus('Opening event');
			}

			/*

			*/
			function activateOnEnterOrSpace(evt, callback)
			{
				if(!evt || !callback)
					return;

				var key = evt.key || '';
				if(key === 'Enter' || key === ' ' || key === 'Spacebar'){
					evt.preventDefault();
					callback(evt);
				}
			}


		/*

		*/
			$(document).ready(function()
			{
				ensureA11yStatusRegion();

					if($('#cdsArchiveSkipLink').length < 1){
						$('body').prepend('<a id="cdsArchiveSkipLink" class="cdsArchiveSkipLink" href="#cdsContent">Skip to main content</a>');
					}

				// /////////////
				$('#cdsContent').delegate('.collapse','show.bs.collapse', function(e)
				{
					var id = e.target.id;
					tabSelect(getIDXFromID(e.target.id));
				});

			// /////////////
				$('#cdsContent').delegate('#ulTabControl a[data-toggle="tab"]','shown.bs.tab', function(e)
				{
					$('#ulTabControl a[data-toggle="tab"]').attr('aria-selected', 'false');
					$(e.target).attr('aria-selected', 'true');
					tabSelect(getIDXFromID(e.target.id));
				});

				// /////////////
				$('#cdsContent').delegate('.cdsEventLaunch', 'click', function(e)
				{
					var launchBtn = $(e.currentTarget);
					var eventID = launchBtn.attr('data-event-id');
					var sourceType = launchBtn.attr('data-source');

					launchArchiveEvent(eventID, sourceType);
				});
				
				// /////////////
				$('#cdsContent').delegate('.cdsEventTable td.tdEventTitle, .cdsEventTable td.tdEventDateTime', 'click', function(e)
				{
					var row = $(e.currentTarget).closest('tr');
					launchArchiveEvent(row.attr('data-event-id'), row.attr('data-source'));
				});

				$('#cdsContent').delegate('.cdsEventLaunch, .cdsEventTable td.tdEventTitle, .cdsEventTable td.tdEventDateTime', 'keydown', function(evt)
				{
					activateOnEnterOrSpace(evt, function(triggerEvt){
						$(triggerEvt.currentTarget).trigger('click');
					});
				});

				// Keep full accordion header click target while retaining button semantics.
				$('#cdsContent').delegate('.cdsAccordionHandle', 'click', function(evt)
				{
					if($(evt.target).closest('.cdsAccordionButton').length > 0){
						return;
					}

					var button = $(evt.currentTarget).find('.cdsAccordionButton').first();
					if(button.length > 0){
						button.trigger('click');
					}
				});

			$('#cdsContent').delegate('.cdsArchiveGroupCalChooser .cdsCalMonthBtn', 'click', function(e)
				{								
					var button = $(e.currentTarget);
					var td = button.closest('td');

					var monthID = button.attr('data-month');
					//console.log('monthID:' + monthID);
					var calChooser = td.closest('.cdsArchiveGroupCalChooser');
					var calChooserID = calChooser.attr('id');
				
				//console.log("calChooserID:" + calChooserID);
				
					if(IS_TANDEM_CHOOSERS)
					{
						$('.cdsArchiveGroupCalChooser td.active').removeClass('active');
						$('.cdsArchiveGroupCalChooser .cdsCalMonthBtn.active').removeClass('active');
						$('.tblCalMonth_' + monthID).addClass('active');
						$('.tblCalMonthBtn_' + monthID).addClass('active');
					}
					else
					{
						calChooser.find('td.active').removeClass('active');
						calChooser.find('.cdsCalMonthBtn.active').removeClass('active');
						td.addClass('active');
						button.addClass('active');
					}
					//only actually RUN for this one...
					populateArchiveGroupEvents(calChooserID.split('_')[1]);


			});

			// /////////////			
			$('#cdsContent').delegate('.cdsArchiveGroupCalChooser .cdsYearSelect', 'change', function(e)
			{								
				var slct = $(e.target);
			
				var pID = slct.closest('.cdsArchiveGroupCalChooser').attr('id');
				if(pID)
				{
					populateArchiveGroupEvents(pID.split('_')[1]);
				}
			});

			// /////////////
			populateArchiveContainer(function(archive, cdseci)
			{
				if(!archive){
					console.log("NO ARCHIVE!");
				}
				else{
					CDSECI = cdseci;
					if(archive.DisplayTypeID == 1){ //accordion
						var firstID = $('#divAccordionControl .panel .collapse.in').attr('id');
						tabSelect(getIDXFromID(firstID));
						
						$('#cdsWrapper').fadeIn(250, function(){	});
					}
					else if(archive.DisplayTypeID == 2){ //tabs
						var firstID = $('#ulTabControl li.active a').attr('id');
						tabSelect(getIDXFromID(firstID));
						
						$('#cdsWrapper').fadeIn(250, function(){ });
					}
				}
			});
		});
