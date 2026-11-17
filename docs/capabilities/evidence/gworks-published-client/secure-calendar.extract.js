function loadCalenderData (calObj, startDate, endDate) {
  window.$gworks.api.postSecure({
    uri: '/cms/secure/city/meeting/list',
    data: {
      range: {
        'cms_meeting.meeting_ts': {
          f: startDate,
          t: endDate
        }
      },
      columns: [
        {
          data: 'cms_meeting.id'
        },
        {
          data: 'cms_meeting.meeting_ts',
          orderable: 'true'
        },
        {
          data: 'cms_meeting.title'
        },
        {
          data: 'cms_meeting.agenda_published_fl'
        }
      ],
      order: [
        {
          column: 1,
          dir: 'asc'
        }
      ],
      start: 0
    },
    fnSuccess: function (data) {
      const calendarEvent = [];
      for (const ref of data.data) {
        let eclass = 'far fa-handshake gworks-evt-minutes';
        if (window.$gworks.core.isCityPortal()) {
          let type = 'minutes';
          if (ref['cms_meeting.agenda_published_fl'] === false) {
            type = 'agenda';
            eclass = 'far fa-clock gworks-evt-agenda';
          }

          calendarEvent.push({
            title: '',
            description: ref['cms_meeting.title'],
            start: ref['cms_meeting.meeting_ts'],
            url: `/plugin/cms/am-editor-${type}.html?cms_meeting.id=${ref['cms_meeting.id']}`,
            allDay: true,
            icon: eclass
          });
        } else {
          if (ref['cms_meeting.agenda_published_fl'] !== false) {
            const linktype = (ref['cms_meeting.minutes_published_fl'] === false) ? 'agenda' : 'minute';

            calendarEvent.push({
              title: '',
              description: ref['cms_meeting.title'],
              start: ref['cms_meeting.meeting_ts'],
              url: `/plugin/cms/agenda-detail.html?cms_meeting.id=${ref['cms_meeting.id']}&type=${linktype}`,
              allDay: true,
              icon: eclass
            });
          }
        }
      }

      window.$gworks.calendar.renderEvent(calObj, calendarEvent);
    },
    fnError: window.$gworks.core.onWarning
  });
}
