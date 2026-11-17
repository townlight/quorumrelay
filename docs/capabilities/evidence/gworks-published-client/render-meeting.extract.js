  renderMeeting () {
    const meetId = window.$gworks.api.getUriParam('cms_meeting.id', null);
    const type = window.$gworks.api.getUriParam('type', null);

    if (meetId == null) {
      window.location.href = '/plugin/cms/agenda-minutes.html';
    }

    $('.gworks-evt-page').load(`${window.$gworks.core.getFileUrl()}/cms/${meetId}_${type}.html`, function (responseText, textStatus, xhr) {
      responseText = window.$gworks.form.getMentions().covertDataToLink(responseText, function (val, name, id) {
        return `<a>@${name}</a>`;
      });

      if (xhr.status === 404) {
        window.location.href = '/plugin/cms/agenda-minutes.html';
      } else {
        $('.gworks-evt-page').html(responseText);
      }
    });
  }
