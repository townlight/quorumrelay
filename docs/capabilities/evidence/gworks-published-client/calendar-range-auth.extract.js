    postSecure(options) {
        options.type = 'POST';
        const _oauth = this.oauth;
        options.fnAuthorization = function () {
          return _oauth.getActiveAccessToken();
        };
        this.__callWithBody(options);
    }



    const params = this.__getAjaxParams(options);

    if (options.externalAPI) {
      params.dataType = ('dataType' in options) ? options.dataType : 'jsonp';
    }
    else {
      params.dataType = ('dataType' in options) ? options.dataType : 'json';
    }

    if (options.contentType && options.contentType === 'application/x-www-form-urlencoded') {
      params.data = options.data;
      params.contentType = 'application/x-www-form-urlencoded';
    }
    else if (options.contentType && options.contentType === 'multipart/form-data') {
      params.data = options.data;
      params.contentType = false;
      params.processData = false;
      params.dataType = 'json';
    }
    else {
      params.data = JSON.stringify(options.data);
      params.contentType = 'application/json';
    }

        this.__performAjax(params);
  }

      };
    } else if (options.fnAuthorization) {
      params.headers = {
        Authorization: 'Bearer ' + ((typeof options.fnAuthorization === 'string') ? options.fnAuthorization : options.fnAuthorization())
      };
    } else {
      params.headers = {};
    }


function loadCalenderEvents(calendar, options) {
  const formattedDate = new Date(calendar.view.activeStart);
  const startdate = formattedDate.getDate();
  const startMonth = formattedDate.getMonth() + 1;
  const startYear = formattedDate.getFullYear();

  const endFormattedDate = new Date(calendar.view.activeEnd);
  const enddate = endFormattedDate.getDate();
  const endMonth = endFormattedDate.getMonth() + 1;
  const endYear = endFormattedDate.getFullYear();

  for (const curevt of calendar.getEvents()) {
    curevt.remove();
  }
  if (options.onDateRender) {
    const startRange = `${startYear}-${startMonth}-${startdate} 00:00:00`;
    const endRange = `${endYear}-${endMonth}-${enddate} 23:59:59`;
    options.onDateRender(calendar, startRange, endRange);
  }
}
