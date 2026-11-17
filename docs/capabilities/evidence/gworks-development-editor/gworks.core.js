(function(){function r(e,n,t){function o(i,f){if(!n[i]){if(!e[i]){var c="function"==typeof require&&require;if(!f&&c)return c(i,!0);if(u)return u(i,!0);var a=new Error("Cannot find module '"+i+"'");throw a.code="MODULE_NOT_FOUND",a}var p=n[i]={exports:{}};e[i][0].call(p.exports,function(r){var n=e[i][1][r];return o(n||r)},p,p.exports,r,e,n,t)}return n[i].exports}for(var u="function"==typeof require&&require,i=0;i<t.length;i++)o(t[i]);return o}return r})()({1:[function(require,module,exports){
!function(t,e){"object"==typeof exports&&"undefined"!=typeof module?module.exports=e():"function"==typeof define&&define.amd?define(e):(t="undefined"!=typeof globalThis?globalThis:t||self).MetisMenu=e()}(this,(function(){"use strict";const t={parentTrigger:"li",subMenu:"ul",toggle:!0,triggerElement:"a"},e={ACTIVE:"mm-active",COLLAPSE:"mm-collapse",COLLAPSED:"mm-collapsed",COLLAPSING:"mm-collapsing",METIS:"metismenu",SHOW:"mm-show"};class s{constructor(e,i){this.element=s.isElement(e)?e:document.querySelector(e),this.config=Object.assign(Object.assign({},t),i),this.disposed=!1,this.triggerArr=[],this.boundEventHandler=this.clickEvent.bind(this),this.init()}static attach(t,e){return new s(t,e)}init(){const{METIS:t,ACTIVE:s,COLLAPSE:i}=e;this.element.classList.add(t);const n=[...this.element.querySelectorAll(this.config.subMenu)];0!==n.length&&n.forEach((t=>{t.classList.add(i);const e=t.closest(this.config.parentTrigger);(null==e?void 0:e.classList.contains(s))?this.show(t):this.hide(t);const n=null==e?void 0:e.querySelector(this.config.triggerElement);"true"!==(null==n?void 0:n.getAttribute("aria-disabled"))&&(null==n||n.setAttribute("aria-expanded","false"),null==n||n.addEventListener("click",this.boundEventHandler),this.triggerArr.push(n))}))}clickEvent(t){if(!this.disposed){const e=null==t?void 0:t.currentTarget;e&&"A"===e.tagName&&t.preventDefault();const s=e.closest(this.config.parentTrigger),i=null==s?void 0:s.querySelector(this.config.subMenu);this.toggle(i)}}update(){this.disposed=!1,this.init()}dispose(){this.triggerArr.forEach((t=>{t.removeEventListener("click",this.boundEventHandler)})),this.disposed=!0}on(t,e,s){return this.element.addEventListener(t,e,s),this}off(t,e,s){return this.element.removeEventListener(t,e,s),this}emit(t,e,s=!1){const i=new CustomEvent(t,{bubbles:s,detail:e});this.element.dispatchEvent(i)}toggle(t){const s=t.closest(this.config.parentTrigger);(null==s?void 0:s.classList.contains(e.ACTIVE))?this.hide(t):this.show(t)}show(t){var s;const i=t,{ACTIVE:n,COLLAPSE:l,COLLAPSED:o,COLLAPSING:r,SHOW:c}=e;if(this.isTransitioning||i.classList.contains(r))return;const a=()=>{i.classList.remove(r),i.style.height="",i.removeEventListener("transitionend",a),this.setTransitioning(!1),this.emit("shown.metisMenu",{shownElement:i})},h=i.closest(this.config.parentTrigger);null==h||h.classList.add(n);const d=null==h?void 0:h.querySelector(this.config.triggerElement);null==d||d.setAttribute("aria-expanded","true"),null==d||d.classList.remove(o),i.style.height="0px",i.classList.remove(l),i.classList.remove(c),i.classList.add(r);const g=[].slice.call(null===(s=null==h?void 0:h.parentNode)||void 0===s?void 0:s.children).filter((t=>t!==h));this.config.toggle&&g.length>0&&g.forEach((t=>{const e=t.querySelector(this.config.subMenu);e&&this.hide(e)})),this.setTransitioning(!0),i.classList.add(l),i.classList.add(c),i.style.height=`${i.scrollHeight}px`,this.emit("show.metisMenu",{showElement:i}),i.addEventListener("transitionend",a)}hide(t){const{ACTIVE:s,COLLAPSE:i,COLLAPSED:n,COLLAPSING:l,SHOW:o}=e,r=t;if(this.isTransitioning||!r.classList.contains(o))return;this.emit("hide.metisMenu",{hideElement:r});const c=r.closest(this.config.parentTrigger);null==c||c.classList.remove(s);const a=()=>{r.classList.remove(l),r.classList.add(i),r.style.height="",r.removeEventListener("transitionend",a),this.setTransitioning(!1),this.emit("hidden.metisMenu",{hiddenElement:r})};r.style.height=`${r.getBoundingClientRect().height}px`,r.style.height=`${r.offsetHeight}px`,r.classList.add(l),r.classList.remove(i),r.classList.remove(o),this.setTransitioning(!0),r.addEventListener("transitionend",a),r.style.height="0px";const h=null==c?void 0:c.querySelector(this.config.triggerElement);null==h||h.setAttribute("aria-expanded","false"),null==h||h.classList.add(n)}setTransitioning(t){this.isTransitioning=t}static isElement(t){return Boolean(t.classList)}}return s}));

},{}],2:[function(require,module,exports){
'use strict';

const OauthClass = require('./oauth');

module.exports = class Api {
  constructor (apiEndPoint) {
    this.apiEndPoint = apiEndPoint;
    this.oauth = new OauthClass(this);
  }

  setFnFailedRefresh (fn) {
    this.oauth.setFnFailedRefresh(fn);
  }

  doLogin (username, password, cityCode, fnGood, fnBad) {
    this.oauth.doLogin(username, password, cityCode, fnGood, fnBad);
  }

  doLoginSupport (token, fnGood, fnBad) {
    this.oauth.doLoginSupport(token, fnGood, fnBad);
  }

  doLoginCitizenSupport (token, fnGood, fnBad) {
    this.oauth.doLoginCitizenSupport(token, fnGood, fnBad);
  }

  doLoginGuestPayments (cityId, cityName, fnGood, fnBad) {
    this.oauth.doLoginGuestPayments(cityId, cityName, fnGood, fnBad);
  }

  isUserLoggedIn () {
    return this.oauth.getActiveAccessToken() != null;
  }

  initSecure () {
    return this.oauth.initSecure();
  }

  setEndPoint (_endPoint) {
    this.apiEndPoint = _endPoint;
  }

  __performAjax (params) {
    const promise = $.ajax(params);

    promise.fail(function () {
      if (params.fnFinally) {
        params.fnFinally();
      }
    });

    promise.done(function () {
      if (params.fnFinally) {
        params.fnFinally();
      }
    });
  }

  getUriParam (parameter, defaultValue) {
    let urlparameter = defaultValue;
    const qM = window.location.href.indexOf('?');
    if (qM > -1 && window.location.href.indexOf(parameter + '=', qM) > -1) {
      const vars = {};
      window.location.href.replace(/[?&]+([^=&]+)=([^&]*)/gi, function (m, key, value) {
        if (value.endsWith('#')) {
          value = value.substr(0, value.indexOf('#'));
        }
        vars[key] = value;
      });
      urlparameter = decodeURI(vars[parameter]);
    }
    return urlparameter;
  }

  getSecureParams (options) {
    options.type = 'GET';

    const _oauth = this.oauth;
    options.fnAuthorization = function () {
      return _oauth.getActiveAccessToken();
    };

    return this.__getAjaxParams(options);
  }

  postSecureParams (options) {
    options.type = 'POST';

    const _oauth = this.oauth;
    options.fnAuthorization = function () {
      return _oauth.getActiveAccessToken();
    };

    return this.__getAjaxParams(options);
  }

  get (options) {
    options.type = 'GET';
    const params = this.__getAjaxParams(options);
    this.__performAjax(params);
  }

  getSecure (options) {
    options.type = 'GET';

       const _oauth = this.oauth;
    options.fnAuthorization = function () {
      return _oauth.getActiveAccessToken();
    };
    const params = this.__getAjaxParams(options);
    this.__performAjax(params);
  }

    getExternalSecure(options) {
        options.type = 'GET';
        if (window.configData.externalApiEndpoint.includes('localhost')) {
            options.uri = options.uri.substring(2);
        }
        else {
          const _oauth = this.oauth;
          if (!options.fnAuthorization) {
              options.fnAuthorization = function(){
                  return _oauth.getToken();
              };
          }
      }
        const params = this.__getAjaxParams(options);
        this.__performAjax(params);
    }

  getAccessToken () {
    return this.oauth.getActiveAccessToken();
  }

  getRefreshToken() {
    return this.oauth.getRefreshToken();
  }

  post (options) {
    options.type = 'POST';
    this.__callWithBody(options);
  }

    postSecure(options) {
        options.type = 'POST';
        const _oauth = this.oauth;
        options.fnAuthorization = function () {
          return _oauth.getActiveAccessToken();
        };
        this.__callWithBody(options);
    }






  postExternalSecure(options){
    options.type = 'POST';
    options.externalAPI = true;
    this.uri = ''
    if (window.configData.externalApiEndpoint.includes('localhost')) {
        options.uri = options.uri.substring(2);
    }
    else {
        const _oauth = this.oauth;
        if (!options.fnAuthorization) {
            options.fnAuthorization = function() {
                return _oauth.getToken();
            };
        }
    }
    this.__callWithBody(options)
    }


    putExternalSecure(options) {

        options.type = 'PUT';
        options.externalAPI = true;
        this.uri = ''
        if (window.configData.externalApiEndpoint.includes('localhost')) {
            options.uri = options.uri.substring(2);
        }
        else {
            const _oauth = this.oauth;
            if (!options.fnAuthorization) {
                options.fnAuthorization = function () {
                    return _oauth.getToken();
                };
            }
        }
        this.__callWithBody(options)

    }

  patch (options) {
    options.type = 'PATCH';
    this.__callWithBody(options);
  }

  patchSecure (options) {
    options.type = 'PATCH';
    const _oauth = this.oauth;
    options.fnAuthorization = function () {
      return _oauth.getActiveAccessToken();
    };
    this.__callWithBody(options);
  }

  put (options) {
    options.type = 'PUT';
    this.__callWithBody(options);
  }

  putSecure (options) {
    options.type = 'PUT';
    const _oauth = this.oauth;
    options.fnAuthorization = function () {
      return _oauth.getActiveAccessToken();
    };
    this.__callWithBody(options);
  }

  deleteSecure (options) {
    options.type = 'DELETE';
    const _oauth = this.oauth;
    options.fnAuthorization = function () {
      return _oauth.getActiveAccessToken();
    };
    this.__callWithBody(options);
  }

  __callWithBody (options) {
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

  __getAjaxParams (options) {
    const params = {
      url: (options.url) ? options.url : this.apiEndPoint + options.uri,
      type: options.type,
      crossDomain: true
    };

    if (options.username && options.password) {
      params.headers = {
        Authorization: 'Basic ' + btoa(options.username + ':' + options.password)
      };
    } else if (options.fnAuthorization) {
      params.headers = {
        Authorization: 'Bearer ' + ((typeof options.fnAuthorization === 'string') ? options.fnAuthorization : options.fnAuthorization())
      };
    } else {
      params.headers = {};
    }

    if (options.contentType) {
      params.contentType = options.contentType;
    }

    if (options.Accept) {
      params.headers.Accept = options.Accept;
    }

    if (options.fnSuccess) {
      params.success = options.fnSuccess;
    }

    if (options.fnFinally) {
      params.fnFinally = options.fnFinally;
    }

    if (options.fnError && options.fnError != null) {
      params.error = function (err) {
        try {
          if (err.responseText) { err = JSON.parse(err.responseText); } else if (err.statusText) { err = err.statusText; }
        } catch (e) {}

        options.fnError(err);
      };
    }

    return params;
  }

  uploadFile (options) {
    if ('file' in options && options.file != null) {
      const fileToUpload = options.file;
      const formData = options.postdata || {};

      for (const ref in formData) {
        if (ref.endsWith('filename')) {
          formData[ref] = fileToUpload.name;
        }
        if (ref.endsWith('mime_type')) {
          formData[ref] = fileToUpload.type;
        }
        if (ref.endsWith('size_kb')) {
          formData[ref] = parseInt(fileToUpload.size / 1000, 10);
        }
      }

      if (options.maxFileSize) {
        if (parseInt(fileToUpload.size / 1000, 10) > Number(options.maxFileSize)) {
          const errMess = `This file exceeds the maximum size of ${options.maxFileSize / 1000} MB`;

          if (options.fnError) {
            window.$gworks.core.onWarning(errMess);
            options.fnError({ error: 'fileSize', msg: errMess });
          } else {
            window.$gworks.core.onWarning(errMess);
          }
          return;
        }
      }

      if (options.allowedExt) {
        if (!this.confirmUserDefinedFileType(fileToUpload.name, options.allowedExt)) {
          const fileExtension = options.allowedExt.split('|');
          window.$gworks.core.onWarning('Allowed file extensions are  : ' + fileExtension.join(', '));
          return;
        }
      }

      window.$gworks.core.onDisplay(null).onDisplay(`
      <div>Uploading Progress</div>
      <div class="gworks-evt-file-progress-name">${fileToUpload.name}</div>
      <div>Progress: <span class="gworks-evt-file-progress-progress">0 %</span></div>
      <div><a class="text-danger" onclick="window.$gworks.fileUpload.cancelUpload()">cancel upload</a></div>
      `, {
        progressBar: false,
        positionClass: 'toast-bottom-right',
        timeOut: 0,
        extendedTimeOut: 0
      });

      window.$gworks.fileUpload = this;
      window.$gworks.options = options;
      const thisInst = this;

      const payload = {
        data: formData,
        contentType: options.contentType,
        fnAuthorization: options.fnAuthorization,
        fnSuccess: function (data) {
          const xhr = new XMLHttpRequest();
          thisInst.xhr = xhr;
          xhr.upload.addEventListener('progress', thisInst.__onProgress, false);
          xhr.addEventListener('error', thisInst.__onError, false);
          xhr.addEventListener('load', function (evt) {
            thisInst.__onComplete(evt, data);
          }, false);
          xhr.open('PUT', data.signedUrl, true);
          xhr.setRequestHeader('Content-Type', fileToUpload.type);
          xhr.send(fileToUpload);
          return data;
        },
        fnError: function (data) {
          console.error(data)
          if (options.fnError) {
            window.$gworks.core.onDisplay(null);
            window.$gworks.options.fnError(data);
          } else {
            window.$gworks.core.onDisplay(null);
            window.$gworks.core.onWarning(data);
          }
        }
      }

      if (options.externalAPI) {
        payload.uri = options.uri
        window.$gworks.externalApi.postExternalSecure(payload);
      }
      else {
        payload.uri = options.url
        window.$gworks.api.postSecure(payload);
      }
    }
  }

  confirmUserDefinedFileType (filename, extType) {
    filename = filename.toLowerCase();
    const fileExtension = extType.split('|');
    if ($.inArray(filename.substr(filename.lastIndexOf('.') + 1), fileExtension) === -1) {
      return false;
    }
    return true;
  }

  cancelUpload () {
    window.$gworks.form.enableButtons();
    window.$gworks.core.standardModal().close();
    if (this.xhr) {
      this.xhr.abort();
      window.$gworks.core.onDisplay(null).onWarning('Upload has been cancelled');
      delete this.xhr;
      delete window.$gworks.fileUpload;
    }
  }

  __onError (evt) {
    if (window.$gworks.options.fnError) {
      window.$gworks.core.onDisplay(null);
      window.$gworks.options.fnError({ error: 'S3error', msg: evt });
    } else {
      window.$gworks.core.onDisplay(null).onError(evt);
    }
    delete window.$gworks.fileUpload.xhr;
    delete window.$gworks.fileUpload;
    delete window.$gworks.options;
  }

  __onComplete (evt, data) {
    $('.gworks-evt-file-progress-progress').html('100 %');
    if (window.$gworks.options.fnSuccess) {
      window.$gworks.core.onDisplay(null);
      window.$gworks.options.fnSuccess(data);
    } else {
      window.$gworks.core.onDisplay(null).onSuccess('File Succesfully Uploaded');
    }
    delete window.$gworks.options;
    delete window.$gworks.fileUpload;
  }

  __onProgress (evt) {
    if (evt.lengthComputable) {
      const percentComplete = Math.round(evt.loaded * 100 / evt.total);
      if (percentComplete < 100) {
        $('.gworks-evt-file-progress-progress').html(percentComplete + ' %');
      }
    }
  }
};

},{"./oauth":32}],3:[function(require,module,exports){
module.exports = {

  init: function (selector, options, timezone) {
    const calendarEl = document.getElementById(selector);
    const calendar = new FullCalendar.Calendar(calendarEl, {
      timeZone: timezone ? timezone : 'local',
      initialView: 'dayGridMonth',
      headerToolbar: {
        start: 'title', 
        center: '',
        end: 'today prevYear,prev,next,nextYear'
      },
      height: 'auto',
      titleFormat: {
        year: 'numeric', month: 'short'
      },
      dateClick: function (date, jsEvent, view) {
        if (options.onDateClick) {
          options.onDateClick(date.dateStr);
        }
      },
      eventContent: function (args, createElement) {
        const icon = args.event._def.extendedProps.icon;
        let text = args.event._def.title;
        if (icon) {
          text = "<em class='" + icon + "'></em> " + args.event._def.title;
        }

        return {
          html: text
        };
      },
      eventDidMount: function (info, element) {
        $('.fc-daygrid-event:last').attr('data-toggle', 'tooltip');
        $('.fc-daygrid-event:last').attr('data-placement', 'top');
        $('.fc-daygrid-event:last').attr('title', info.event.extendedProps.description);
      }
    });
    setTimeout(function () {
      calendar.render();
      calendarEl.querySelector('.fc-today-button').addEventListener('click', function () {
        loadCalenderEvents(calendar, options);
      });
    }, 100);
    loadCalenderEvents(calendar, options);

    $('body').on('click', 'button.fc-prev-button', function () {
      loadCalenderEvents(calendar, options);
    });

    $('body').on('click', 'button.fc-next-button', function () {
      loadCalenderEvents(calendar, options);
    });

    $('body').on('click', 'button.fc-prevYear-button', function () {
      loadCalenderEvents(calendar, options);
    });

    $('body').on('click', 'button.fc-nextYear-button', function () {
      loadCalenderEvents(calendar, options);
    });

    return this;
  },

  renderEvent: function (cal, events) {
    for (const event of events) {
      cal.addEvent(event);
    }
  }

};

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

},{}],4:[function(require,module,exports){

var webFeaturesList = [];

module.exports = {

  protect: function (entityList) {
    if (!this.hasRO(entityList)) {
      const e = new Error();
      e.redirect = '/s/warning-access.html';
      throw e;
    }
  },

  protectRW: function (entityList) {
    if (!this.hasRW(entityList)) {
      const e = new Error();
      e.redirect = '/s/warning-access.html';
      throw e;
    }
  },

  hasRO: function (entityList) {
    if (!window.$gworks.core.isUserLoggedIn() || window.configData.siteMode === 'citizen') {
      return true;
    }

    const en = entityList.replace(/ /g, '').split(',');
    en.push('SuperAdmin');

    for (const entity of en) {
      if (entity in SECURITY_ENTITY &&
        'acl' in window.$gworks.authUser &&
        window.$gworks.authUser.acl != null &&
        SECURITY_ENTITY[entity] in window.$gworks.authUser.acl &&
        window.$gworks.authUser.acl[SECURITY_ENTITY[entity]].lvl >= 0) {
        return true;
      }
    }

    return false;
  },

  hasRW: function (entityList) {
    const en = entityList.replace(/ /g, '').split(',');
    en.push('SuperAdmin');

    for (const entity of en) {
      if (
        entity in SECURITY_ENTITY &&
        'acl' in window.$gworks.authUser &&
        window.$gworks.authUser.acl != null &&
        SECURITY_ENTITY[entity] in window.$gworks.authUser.acl &&
        window.$gworks.authUser.acl[SECURITY_ENTITY[entity]].lvl >= 1) {
        return true;
      }
    }

    return false;
  },

  hasFull: function (entityList) {
    const en = entityList.replace(/ /g, '').split(',');
    en.push('SuperAdmin');

    for (const entity of en) {
      if (entity in SECURITY_ENTITY &&
        'acl' in window.$gworks.authUser &&
        window.$gworks.authUser.acl != null &&
        SECURITY_ENTITY[entity] in window.$gworks.authUser.acl &&
        window.$gworks.authUser.acl[SECURITY_ENTITY[entity]].lvl >= 2) {
        return true;
      }
    }

    return false;
  },

};


const SECURITY_ENTITY = {
  SuperAdmin: 1,
  Citizen: 2,
  PluginPayments: 4,
  PluginUtilities: 5,
  Plugin311: 9,
  FAMDesktop: 10,
  HR: 11,
  HRFamDesktop: 60,
  HRPortal: 61,
  HRSecure: 62,
  PluginMessagingMessage: 20,
  PluginMessagingPublicNotice: 21,
  PluginMessagingPublicMeetings: 22,
  PluginMessagingPublicFAQ: 23,
  PluginMessagingPages: 24,
  PluginMessagingWebsiteSettings: 25,
  CitizenFiles: 30,
  CitizenAudit: 31,
  CitizenSecure: 32,
  SettingsRefTypes: 41,
  SettingsPayment: 42,
  SettingsBase: 43,
  SettingsPDF: 44,
  Reports: 50,
  PluginReports: 50,
  PluginForms: 7,
  PluginFormsManager: 70,
  FinanceAccounting: 135,
  FinanceAccountsReceivable: 136,
  FinanceAccountsPayable: 137,
  FinanceBudgeting: 138,
  FinanceReports: 139,
  FinanceSettings: 140,
  CourtTickets: 175,
  CourtCases: 176,
  CourtDefendantRepository: 177,
  CourtReporting: 178,
  CourtSettings: 179
};

},{}],5:[function(require,module,exports){
module.exports = {

  init: function (selector, fnCallback, initialFilter) {
    $(selector).datacard = new DataCard($(selector), fnCallback, initialFilter);
    return $(selector).datacard;
  }

};


class DataCard {
  constructor (jqEl, fnCallback, intialFilter) {
    this.fnCallback = typeof fnCallback !== 'undefined' ? fnCallback : null;
      this.jqEl = jqEl;
      this.initialFilter = intialFilter;
    this.__setupPaging();
    this.__setupFilter();
    this.fetchData();
  }

  __getAttr (name) {
    const attr = this.jqEl.attr(name);
    return ((typeof attr === 'undefined') || attr.trim() === '') ? null : attr.trim();
  }

  __showLoading () {
    this.__setTotal('-');
    this.jqEl.html(window.$gworks.core.getLoadingHtml());

    if (this.__getAttr('datacard-paging') != null) {
      $(`#${this.pagingId}`).hide();
    }
  }

  __setupPaging () {
    this.currentOffset = 0;
    const pageSize = this.__getAttr('datacard-paging');
    if (pageSize == null) {
      return;
    }
    this.jqEl.attr('datacard-limit', Number(pageSize));

    this.pagingId = new Date().getTime();
    this.jqEl.after(`
      <ul class="pagination mt-3 justify-content-end" id="${this.pagingId}">
        <li class="page-item">
          <a class="page-link  gworks-evt-page-left" aria-label="Previous"><i class="fal fa-angle-double-left"></i></a>
        </li>
        <li class="page-item active">
          <div class="datacard-page-no page-link"></div>
        </li>
        <li class="page-item">
          <a class="page-link  gworks-evt-page-right" aria-label="Next"><i class="fal fa-angle-double-right"></i></a>
        </li>
      </ul>
    `);

    const thisInst = this;
    $(`#${this.pagingId} .gworks-evt-page-left`).on('click', function () {
      if (thisInst.currentOffset === 0) {
        return;
      }

      thisInst.currentOffset -= Number(pageSize);
      if (thisInst.currentOffset < 0) {
        thisInst.currentOffset = 0;
      }
      thisInst.fetchData();
    });

    $(`#${this.pagingId} .gworks-evt-page-right`).on('click', function () {
      thisInst.currentOffset += Number(pageSize);
      if (thisInst.currentOffset >= thisInst.totalRecords) {
        thisInst.currentOffset -= Number(pageSize);
        return;
      }
      thisInst.fetchData();
    });
  }

  __updatePaging (total) {
    const pageSize = this.__getAttr('datacard-paging');
    if (pageSize == null) {
      return;
    }

    if (total <= Number(pageSize)) {
      $(`#${this.pagingId}`).hide();
      return;
    }

    const totalPages = Math.ceil(total / Number(pageSize));
    const currPage = 1 + Math.ceil(this.currentOffset / Number(pageSize));

    $(`#${this.pagingId} .datacard-page-no`).html(`${currPage} of ${totalPages}`);
    $(`#${this.pagingId}`).show();
  }

  __setupFilter () {
    const filter = this.__getAttr('datacard-filter');
    if (filter == null) {
      return;
    }

    require('./filter').setupAll(this, filter);
  }

  __fetchFilterParams () {
    let filter = this.__getAttr('datacard-filter');
    filter = (filter == null) ? {} : require('./filter').fetchParams(filter);
    console.log(filter);
    const order = this.__getAttr('datacard-order-column');
    if (order != null) {
      let orderby = this.__getAttr('datacard-order-dir');

      if (filter.order && filter.order.length > 0) {
        orderby = filter.order;
      } else {
        orderby = (orderby == null) ? ['asc'] : orderby.split(',');
      }

      const cols = order.split(',');
      filter.columns = [];
      filter.order = [];

      for (const col of cols) {
        filter.columns.push({
          data: col.trim(),
          orderable: 'true'
        });

        filter.order.push({
          column: filter.order.length,
          dir: orderby.length <= filter.order.length ? orderby[filter.order.length] : orderby[0]
        });
      }
    }

    const limit = this.__getAttr('datacard-limit');
    if (limit != null) {
      filter.start = this.currentOffset;
      filter.length = Number(limit);
    }

    return filter;
  }

  fetchData () {
      let uri = this.__getAttr('datacard-uri');
    if (uri == null) {
      return;
    }

    uri = uri.replace(':personId', window.$gworks.core.getUserId());
    uri = uri.replace(':person.id', window.$gworks.api.getUriParam('person.id', '-1'));

    this.__showLoading();

    const filterParams = this.__fetchFilterParams();
    console.log(filterParams);
    const thisInst = this;
    const options = {
      uri: uri,
      data: filterParams,
      fnSuccess: function (inData) {
        thisInst.__renderData(inData);

        if (thisInst.fnCallback != null) {
          thisInst.fnCallback(thisInst);
        }
      }
      };

    const method = this.__getAttr('datacard-method') == null ? 'POST' : this.__getAttr('datacard-method').toUpperCase();
      if (method === 'POST') {
          var pageNumber = 1;
          if (this.currentOffset >= 10) {
              pageNumber = (this.currentOffset)/10 + 1;
          }
        if (uri.startsWith('/o/api/')) {
            var pagination = JSON.parse('{ "pageSize": ' + this.__getAttr('datacard-paging') + ', "pageNumber":' + pageNumber + '}')
            var filter = "";
            console.log(filterParams.equals.status);
            if (filterParams.equals.status != "All" && typeof filterParams.equals.status !== 'undefined')
            {
                filter = JSON.parse('[{"name":"status","appliedFilters":["' + filterParams.equals.status + '"]}, {"name": "applicant","appliedFilters": ["' + window.$gworks.core.getUserId().toString() + '"]}]')
            }
            else
            {
                filter = JSON.parse('[{"name": "applicant","appliedFilters": ["' + window.$gworks.core.getUserId().toString() + '"]}]');
            }
            console.log(filter);
            var gridType = this.__getAttr('datacard-grid-type')
            if (gridType !== null && gridType !== '' && !isNaN(gridType)) {
                gridType = parseInt(gridType);
            }
            window.$gworks.externalApi.postExternalSecure({
                uri: uri,
                data: {
                    gridType: gridType,
                    pagination: pagination,
                    columns: filter
                },
                dataType: 'json',
                Accept: 'application/json',
                fnSuccess: async function (data) {
                    thisInst.__renderData(data.data.data, data.data.pagination.totalRecords);
                },
                fnError: function (data) {
                    window.$gworks.core.loadingOff();
                    window.$gworks.core.onWarning(data);
                }
            });
        }
        else {
            window.$gworks.api.postSecure(options);
        }
    } else {
      window.$gworks.api.getSecure(options);
    }
  }

  __renderData (inData, totalRecords) {
      if (Array.isArray(inData)) {
      inData = {
        data: inData
        };
        if (totalRecords !== null) {
            inData.recordsTotal = totalRecords;
            console.log(totalRecords);
        }
        else {
            inData.recordsTotal = inData.data.length;
        }
    }

    if (inData.data.length === 0) {
      const nodataTemplate = this.__getAttr('datacard-nodata-template');
      if (nodataTemplate != null) {
        this.jqEl.html($(nodataTemplate).html());
      }

      const nodataSelector = this.__getAttr('datacard-nodata-selector');
      if (nodataSelector != null) {
        $(nodataSelector).hide();
      }

      this.__setTotal('0');
      this.__updatePaging(0);
      return;
    } else if (this.__getAttr('datacard-row-template') == null) {
      return;
    }

    let html = '';
    const TEMPLATE = $(this.__getAttr('datacard-row-template')).html();
      for (const row of inData.data) {
          const data = this.__attachHelpers(window.$gworks.core.flattenScope(row));
          html += Mustache.render(TEMPLATE, data);
    }

    this.__setTotal(inData.recordsTotal);
    this.__updatePaging(inData.recordsTotal);
    this.jqEl.html(html);

    const nodataSelector = this.__getAttr('datacard-nodata-selector');
    if (nodataSelector != null) {
      $(nodataSelector).show();
    }
  }

  __setTotal (v) {
    this.totalRecords = Number(v);
    const totalSelector = this.__getAttr('datacard-total');
    if (totalSelector != null) {
      $(totalSelector).html(v);
    }
  }

  __attachHelpers (data) {
    data.DateShort = function () {
      return function (val, render) {
        return window.$gworks.core.renderDateShort(render(val));
      };
    };

    data.DateLong = function () {
      return function (val, render) {
        return window.$gworks.core.renderDateLong(render(val));
      };
    };

    data.DateShortUtc = function () {
      return function (val, render) {
        return window.$gworks.core.renderDateShortUtc(render(val));
      };
    };

    data.DateLongUtc = function () {
      return function (val, render) {
        return window.$gworks.core.renderDateLongUtc(render(val));
      };
    };

    data.Time = function () {
      return function (val, render) {
        return window.$gworks.core.renderTime(render(val));
      };
    };

    data.MonthName = function () {
      return function (val, render) {
        return window.$gworks.core.renderMonthName(render(val));
      };
    };

    data.Currency = function () {
      return function (val, render) {
        return window.$gworks.core.renderCurrency(render(val), true);
      };
    };

    data.CurrencyShort = function () {
      return function (val, render) {
        return window.$gworks.core.renderCurrency(render(val), false);
      };
    };

    data.toLowerCase = function () {
      return function (val, render) {
        return render(val).toLowerCase();
      };
    };

    data.eval = function () {
      return function (val, render) {
        let jsBlock = render(val);
        if (jsBlock.indexOf('<pre>')) {
          jsBlock = jsBlock.substring(jsBlock.indexOf('<pre>') + 5);
        }
        if (jsBlock.indexOf('</pre>')) {
          jsBlock = jsBlock.substring(0, jsBlock.indexOf('</pre>'));
        }

        jsBlock = `() => { ${jsBlock.trim()}}`;
        try {
          const fn = eval(jsBlock);
          const v = fn();
          return (typeof v !== 'undefined' && v != null) ? v : '';
        } catch (e) {
          console.error('---- error ----');
          console.error(e);
          console.error(jsBlock);
          return '--ERROR see console--';
        }
      };
    };

    return data;
  }
}

},{"./filter":8}],6:[function(require,module,exports){

module.exports = {

  doConfig: function (jqSelector, config) {
    config.featureFilter = ('featureFilter' in config) ? config.featureFilter : false;
    config.filterInline = ('filterInline' in config) ? config.filterInline : false;
    config.featureSearch = ('featureSearch' in config) ? config.featureSearch : true;
    config.featureFullLength = ('featureFullLength' in config) ? config.featureFullLength : false;

    config = Object.assign({
      dom: "<'row align-items-end'<'col-sm-12 col-md-3 datatable-search'f><'col-sm-12 col-md-9 gworks-evt-filterarea gworks-filter'>>" +
        "<'row my-3'<'col-sm-12'tr>>" +
        "<'row'<'col-sm-12 col-md-5'<'gworks-evt-tableExportButtons'>><'col-sm-12 col-md-7 d-flex align-items-center justify-content-end'ilp>>",
      serverSide: true,
      autoWidth: true,
      processing: true,
      pageLength: 10,
      searchDelay: 500,
      searchOnEnter: false,
      scrollX: false,
      initComplete: function (settings, json) {
        $(jqSelector).wrap("<div class='responsive-table'></div>");
      },
      columnDefs: [{
        orderable: false,
        searchable: false,
        bSortable: false,
        targets: '_all',
        defaultContent: '<i>n/a</i>'
      }],
      language: {
        paginate: {
          previous: '<i class="fal fa-angle-left"></i>',
          next: '<i class="fal fa-angle-right"></i>',
          first: '<i class="fal fa-angle-double-left"></i>',
          last: '<i class="fal fa-angle-double-right"></i>'
        },
        search: '',
        lengthMenu: '_MENU_ per page'
      }
    }, config);

    if (config.featureSelect) {
      config.select = {
        style: 'multi',
        selector: 'td:first-child'
      };
      const lastIndex = 0;
      config.columns[lastIndex].className = 'select-checkbox';
      config.columns[lastIndex].checkboxes = { selectRow: true };
      config.columns[lastIndex].aTargets = [1];
      config.columns[lastIndex].targets = 0;
      config.columns[lastIndex].bSortable = false;
      config.columns[lastIndex].orderable = false;
      config.columns[lastIndex].render = function () { return ''; };

      if (config.filterRowSelect) {
        config.filterRowSelect.excludeClass = config.filterRowSelect.excludeClass || '';
        config.filterRowSelect.excludeClass = (config.filterRowSelect.excludeClass !== '') ? (config.filterRowSelect.excludeClass + ',select-checkbox sorting_1') : 'select-checkbox sorting_1';
      }

      config.initComplete = function (settings, json, personId) {
        $(jqSelector).find('.select-checkbox.sorting_asc').removeClass('sorting_asc');
        $(jqSelector).wrap("<div class='responsive-table'></div>");
      };
    }

    if (config.featureFilter) { 
      require('./filter').setupPre($(jqSelector).attr('filter-id'));
    }

    if (config.filterRowSelect) {
      config.createdRow = function (row, data, dataIndex) {
        const keys = config.filterRowSelect.keys.split(',');
        for (const key of keys) {
          $(row).attr(key.trim(), data[key.trim()]);
        }
        $(row).attr('href', config.filterRowSelect.href);
      };
    }

    if (config.timezone) {
      $(jqSelector).attr('data-timezone', config.timezone);
    }

    config.ajax = dtAjaxCall(config);
    const dtInst = $(jqSelector).DataTable(config);

    if (config.featureFullLength) {
      $(`${jqSelector}_wrapper .datatable-search`).html('<div class="d-inline-block">	</div>');
			$(`${jqSelector}_wrapper .datatable-search div`).append('<button class="btn btn-secondary" id="fd-payout-reconciliation" type="button">Payout reconciliation report</button>');
    }

    if (!config.featureSearch) {
      $(`${jqSelector}_wrapper .datatable-search`).empty();
    }

    if (config.featureFilter) {
      if (config.filterInline) { 
        let filterId = $(jqSelector).attr('filter-id');
        const filterDestSel = `${jqSelector}_wrapper .gworks-evt-filterarea`;
        $(filterDestSel).html($(filterId).html());
        $(filterId).remove();
        filterId = filterDestSel;
        $(jqSelector).attr('filter-id', filterId);
      }

      dtInst.fetchData = dtInst.ajax.reload;
      require('./filter').setupCallback(dtInst, $(jqSelector).attr('filter-id'));
    }

    if (config.featureSelect) {
      if (config.showFeatureDropdown !== false) {
        $(`${jqSelector} tbody`).on('click', 'td.select-checkbox', function () {
          const tr = $(this).closest('tr');
          const rowData = dtInst.row(tr[0]).data();
          setTimeout(function () {
            rowSelected(dtInst, config.featureSelect, jqSelector, tr, rowData);
          }, 1);
        });
      }

      $(`${jqSelector}_wrapper .gworks-evt-tableExportButtons`).on('change', 'select.gworks-evt-action', function () {
        const v = $(this).val();
        $('.gworks-evt-mailinglist').hide();
        if (v === '') {
        } else if (v === 'clearall') {
          dtInst.selectedRows = [];
          $(`${jqSelector}_wrapper tr`).removeClass('selected');
          dtInst.rows().deselect();
          $(this).remove();
          $(`${jqSelector}_wrapper .gworks-evt-tableExportButtons select`).hide();
        } else {
          for (const ft of config.featureSelect) {
            if (ft.label === v && ft.func) {
              const selectedRows = [];
              for (const k in dtInst.selectedRows) {
                selectedRows.push(JSON.parse(k));
              }
              ft.func(dtInst, selectedRows);
            }
          }
        }
      });
    }

    if (config.featureExport) {
      $(`${jqSelector}_wrapper .gworks-evt-tableExportButtons`).append('<button class="btn btn-secondary ml-1" data-toggle="modal" data-target="#gworks-evt-standardModal"><i class="fa fa-file-export"></i> Export</button>');
    }

    if (config.featureSchedule) {
      $(`${jqSelector}_wrapper .gworks-evt-tableExportButtons`).append('<button class="btn btn-secondary ml-1" data-toggle="modal" data-target="#gworks-evt-standardModal"><i class="fa fa-user-clock"></i> Schedule</button>');
    }

    if (config.filterRowSelect) {
      $(jqSelector).on('click', 'tbody tr td', function (e) {
        if ($(this).hasClass('select-checkbox')) {
          return;
        } else if (config.filterRowSelect.excludeClass) {
          const classCheck = config.filterRowSelect.excludeClass.split(',');
          for (const clas of classCheck) {
            if ($(this).hasClass(clas)) {
              return;
            }
          }
        }

        const tr = $(this).parent();
        const uriParams = [];
        const keyParams = {};
        const keys = config.filterRowSelect.keys.split(',');
        for (const key of keys) {
          if (!tr.attr(key)) {
            break;
          }
          uriParams.push(`${key}=${tr.attr(key)}`);
          keyParams[key] = tr.attr(key);
        }

        if (config.filterRowSelect.fnOnClick && uriParams.length) {
          config.filterRowSelect.fnOnClick(tr, uriParams.join('&'), keyParams);
        } else if (tr.attr('href') != null && uriParams.length) {
          const d = tr.attr('href').indexOf('?') === -1 ? '?' : '&';
          window.location.href = tr.attr('href') + d + uriParams.join('&');
        }
      });
    }

    let timeoutId = null;

    $(`${jqSelector}_wrapper .dataTables_filter input`).unbind().bind('keyup search', function (e) {
      const inputValue = $(this).val().trim();

      (timeoutId != null) && clearTimeout(timeoutId);

      if (inputValue.length >= 3) {
        if (config.searchOnEnter) {
          if (e.keyCode === 13) {
            timeoutId = setTimeout(function () {
              const searchVal = $(`${jqSelector}_wrapper .dataTables_filter input`).val().trim();
              (searchVal.length >= 3) && dtInst.search(searchVal).draw();
            }, config.searchDelay);
          }
        } else {
          timeoutId = setTimeout(function () {
            const searchVal = $(`${jqSelector}_wrapper .dataTables_filter input`).val().trim();
            (searchVal.length >= 3) && dtInst.search(searchVal).draw();
          }, config.searchDelay);
        }
      } else if (inputValue === '') {
        timeoutId = setTimeout(function () {
          dtInst.search('').draw();
        }, config.searchDelay);
      }
    });

    return dtInst;
  },

  reload: function (dtInst) {
    dtInst.ajax.reload();
  },

  renderDateTimeLongUtc: function (data, type, row, meta) {
    if (type === 'display') {
      if (data == null) {
        return '';
      } else {
        const d = moment(data).utc();
        return `<div class='small'>${d.format('ll')}</div><div class='small'>${d.format('LTS')}</div>`;
      }
    } else {
      return data;
    }
  },

  renderDateTimeLong: function (data, type, row, meta) {
    if (type === 'display') {
      if (data == null) {
        return '';
      } else {
        const d = moment(data);
        return `<div class='small'>${d.format('ll')}</div><div class='small'>${d.format('LTS')}</div>`;
      }
    } else {
      return data;
    }
  },

  renderDateMmDdYyyyUtc: function (data, type, row, meta) {
    if (type === 'display') {
      return window.$gworks.core.renderDateShortUtc(data);
    } else {
      return data;
    }
  },

  renderDateMmDdYyyy: function (data, type, row, meta) {
    if (type === 'display') {
      return window.$gworks.core.renderDateShort(data);
    } else {
      return data;
    }
  },

  renderDateMmDdYyyyLong: function (data, type, row, meta) {
    if (type === 'display') {
      return window.$gworks.core.renderDateLong(data);
    } else {
      return data;
    }
  },

  renderDateDay: function (data, type, row, meta) {
    return moment(data).diff(moment(), 'days');
  },

  renderDateDayAsc: function (data, type, row, meta) {
    return moment().diff(moment(data), 'days');
  },

  renderRefLabel: function (data, type, row, meta) {
    if (data == null || data === '') {
      return '';
    } else {
      return window.$gworks.lookup.getLabel(data);
    }
  },

  renderBoolean: function (data, type, row, meta) {
    if (type === 'display') {
      return !data ? '' : '<i class="fad fa-check-circle text-success" aria-hidden="true"></i>';
    } else {
      return data;
    }
  },

  renderBlankIfNull: function (data, type, row, meta) {
    return !data ? '' : data;
  },

  renderBlankIfZero: function (data, type, row, meta) {
    return !data || data === 0 ? '' : data;
  },

  renderPersonUpdate: function (data, type, row, meta) {
    return 'PLEASE UPDATE CODE';
  },

  renderBlank: function () {
    return '';
  },

  renderDaysAge: function (data, type, row, meta) {
    if (data == null || data === '') {
      return '';
    }

    const diffDays = moment(data).diff(moment(), 'days');
    if (diffDays > 0) {
      return (diffDays !== 1) ? `${diffDays} days left` : '1 day left';
    } else {
      return (diffDays !== -1) ? `${diffDays} days over` : '1 day over';
    }
  }

};


function rowSelected (dtInst, featureSelect, jqSelector, tr, rowData) {
  dtInst.selectedRows = dtInst.selectedRows || {};

  const k = JSON.stringify(rowData);
  if (tr.hasClass('selected')) {
    dtInst.selectedRows[k] = true;
  } else {
    delete dtInst.selectedRows[k];
  }

  const btnLeft = $(jqSelector + '_wrapper .gworks-evt-tableExportButtons');
  if (Object.keys(dtInst.selectedRows).length === 0) {
    btnLeft.find('select.gworks-evt-action').remove();
    btnLeft.find('select').hide();
  } else if (btnLeft.find('select.gworks-evt-action').length === 0) {
    let selectHtml = '<select class="gworks-evt-action form-control"><option value="">- Action</option>';
    for (const ft of featureSelect) {
      selectHtml += `<option value='${ft.label}'>${ft.label}</option>`;
    }
    selectHtml += '<option value="clearall">- Clear All</option></select>';
    btnLeft.prepend(selectHtml);
  }
}


function dtAjaxCall (options) {
  const url = options.url;
  const params = window.$gworks.api.postSecureParams({
    uri: url,
    fnError: 'fnError' in options ? options.fnError : null
  });

  params._url = params.url;

  return function (data, fnCallback, settings) {
    params.data = dtAjaxDataClean(data, settings.sTableId);
    if(params.url.match(/transactions/)) {
      window.$gworks.dataTransactions = {...params.data}
    }

    if ('filter' in options) {
      if (typeof params.data.equals === 'undefined') {
        params.data.equals = {};
      }
      for (const f in options.filter) {
        params.data.equals[f] = options.filter[f];
      }
    }


    if ('postBody' in options) {
      for (const k in options.postBody) {
        params.data[k] = options.postBody[k];
      }
    }

    params.success = fnCallback;

    if ('payments_payrix_disbursements.status_code' in params.data.equals) {
      const transformed_params = setPayrixDisbursementStatus(params);
      $.ajax(transformed_params);
    } else {
      $.ajax(params);
    }
  };
}

function setPayrixDisbursementStatus (params){
  if (params.data.equals['payments_payrix_disbursements.status_code'] === 'pending') {
    params.data.equals['payments_payrix_disbursements.status_code'] = ['1', '2'];
  } else if (params.data.equals['payments_payrix_disbursements.status_code'] === 'failed') {
    params.data.equals['payments_payrix_disbursements.status_code'] = ['4', '5', '6'];
  } else {
    params.data.equals['payments_payrix_disbursements.status_code'] = '3';
  }
  return params
  }


function dtAjaxDataClean (data, jqSelector) {
  const filterData = require('./filter').fetchParams($('#' + jqSelector).attr('filter-id'));

  data = Object.assign(data, filterData);

  if (data.length && data.length === -1) {
    data.length = 100;
  }

  if (data.search) {
    delete data.search.regex;
    if (data.search.value === '') {
      delete data.search;
    }
  }

  if (data.columns && data.draw) {
    for (const column of data.columns) {
      if (!column.searchable || !data.search) { delete column.searchable; }
      if (!column.orderable) { delete column.orderable; }

      delete column.name;
      delete column.search;

      const s = column.data.indexOf('\\');
      if (column.data && s > 0) {
        column.data = column.data.substring(0, s) + column.data.substring(s + 1);
      }
    }
  }

  delete data.fieldList;
  return data;
}

},{"./filter":8}],7:[function(require,module,exports){
module.exports = {

  renderGroup: function (groupName, data) {
    doElements(`[display-group=${groupName}]`, 'body', data);
    return this;
  },

  render: function (selector, data) {
    if (typeof selector === 'object') {
      data = selector;
      selector = 'body';
    }
    doElements('[display-name]', selector, data);
    return this;
  }

};


function doElements (displaySelector, selector, data) {
  $(selector).find(displaySelector).each(function () {
    const el = $(this);

    const displayName = getAttr(el, 'display-name');
    if (displayName == null) {
      return;
    }

    let val = null;
    if (!(displayName in data) || data[displayName] == null) {
      val = getAttr(el, 'display-default');
    } else {
      val = data[displayName];
    }

    if (val == null) {
      const hideOnNull = getAttr(el, 'display-hide-on-null');
      if (hideOnNull !== null) {
        if (hideOnNull === '') {
          $(this).hide();
        } else {
          $(hideOnNull).hide();
        }
      }

      const showOnNull = getAttr(el, 'display-show-on-null');
      if (showOnNull !== null) {
        if (showOnNull === '') {
          $(this).show();
        } else {
          $(showOnNull).show();
        }
      }

      return;
    } else {
      const hideOnNotNull = getAttr(el, 'display-hide-notnull');
      if (hideOnNotNull != null) {
        if (hideOnNotNull === '') {
          $(this).hide();
        } else {
          $(hideOnNotNull).hide();
        }
        return;
      }

      const showOnNotNull = getAttr(el, 'display-show-notnull');
      if (showOnNotNull != null) {
        if (showOnNotNull === '') {
          $(this).show();
        } else {
          $(showOnNotNull).show();
        }
      }
    }

    const showOn = getAttr(el, 'display-show-on');
    const hideOn = getAttr(el, 'display-hide-on');

    if (showOn != null || hideOn != null) {
      const showHideEl = getAttr(el, 'display-showhide-selector') == null ? $(this) : $(getAttr(el, 'display-showhide-selector'));

      if (showOn != null && isEqual(val, showOn)) {
        showHideEl.show();
      }

      if (hideOn != null && isEqual(val, hideOn)) {
        showHideEl.hide();
      }
    }

    const format = (typeof el.attr('display-format') !== 'undefined') ? el.attr('display-format').toLowerCase() : 'string';
    switch (format) {
      case 'string':
        el.html(val);
        break;
      case 'date':
        el.html(window.$gworks.core.renderDateShort(val));
        break;
      case 'datelong':
        el.html(window.$gworks.core.renderDateLong(val));
        break;
      case 'time':
        el.html(window.$gworks.core.renderTime(val));
        break;
      case 'datetime':
        el.html(window.$gworks.core.renderDateLongTime(val));
        break;
      case '$$':
        el.html(window.$gworks.core.renderCurrency(val, true));
        break;
      case '$':
        el.html(window.$gworks.core.renderCurrency(val, false));
        break;
      case '%%':
        el.html(window.$gworks.core.renderPercentage(val, true));
        break;
      case '%':
        el.html(window.$gworks.core.renderPercentage(val, false));
        break;
      case 'phone':
        el.html(window.$gworks.core.renderPhone(val, false));
        break;
      case 'reftype':
        el.html(window.$gworks.lookup.getLabel(val));
        break;
      case 'flag':
        el.html(!val ? '' : '<i class="fad fa-check-circle text-success" aria-hidden="true"></i>');
        break;
      case 'void':
        break;
      default:
        console.error(`---] window.$gworks.core.display; unknown format ${format}`);
        el.html(val);
    }
  });
}

function getAttr (el, name) {
  const v = el.attr(name);
  return typeof v === 'undefined' ? null : v;
}

function isEqual (lhs, rhs) {
  const lhsType = typeof lhs;
  const rhsType = typeof rhs;

  if (lhsType === rhsType) {
    return lhs === rhs;
  } else if (lhsType === 'boolean' || rhsType === 'boolean') {
    return String(lhs) === String(rhs);
  } else if (lhsType === 'number' || rhsType === 'number') {
    return Number(lhs) === Number(rhs);
  } else {
    return lhs === rhs;
  }
}

},{}],8:[function(require,module,exports){

module.exports = {

  setupAll: function (dataCard, selector) {
    this.setupPre(selector);
    this.setupCallback(dataCard, selector);
  },

  setupPre: function (selector) {
    window.$gworks.form.init(selector);

    $(selector).find('select.filter').each(function () {
      if ($(this).hasClass('rangefilter')) { return; }

      const blankVal = (typeof $(this).attr('gworks-ref-blank-value') === 'undefined') ? '' : $(this).attr('gworks-ref-blank-value');
      if (blankVal !== '') {
        $(this).attr('filter-val', blankVal);
      } else if ($(this).attr('value') !== '') {
        $(this).attr('filter-val', $(this).attr('value'));
      }

      const uriValue = window.$gworks.api.getUriParam($(this).attr('filter-name'), null);
      if (uriValue != null) {
        $(this).attr('filter-val', uriValue).attr('value', uriValue);
      }
    });

    $(selector).find('input.filter').each(function () {
      const blankVal = (typeof $(this).attr('gworks-ref-blank-value') === 'undefined') ? '' : $(this).attr('gworks-ref-blank-value');
      if (blankVal !== '') {
        $(this).attr('filter-val', blankVal);
      }
    });
  },

  setupCallback: function (dataCard, selector) {
    $(selector).find('.gworks-evt-sortingFilter').each(function () {
      const option = '<option value="desc">Newest First</option><option value="asc">Oldest First</option>';
      $(this).html(option);
      $(this).val($(this).attr('filter-order-by'));
    });

    $(selector).find('select.filter').on('change', function () {
      if ($(this).hasClass('rangefilter')) {
        if ($('option:selected', this).attr('filter-from')) {
          $(this).attr('filter-val', '');
          $(this).attr('filter-from', $('option:selected', this).attr('filter-from'));
          $(this).attr('filter-to', $('option:selected', this).attr('filter-to'));
        } else {
          $(this).removeAttr('filter-from').removeAttr('filter-to');
        }
      }

      if ($(this)[0].hasAttribute('filter-order-by')) {
        $(this).attr('filter-order-by', $(this).val());
      }

      $(this).attr('filter-val', $(this).val());
      dataCard.fetchData();
    });

        if (Object.keys($('#select-multiple-hubs')).length) {
    $('#select-multiple-hubs').select2({
      placeholder: "All",
      allowClear: false
    })
  }

    $(selector).find('.gworks-evt-datepicker').each(function () {
      let filterLabel = $(this).attr('filter-label');
      if (!filterLabel || filterLabel === '') {
        filterLabel = 'All';
      }
      $(this).html('<i class="fad fa-calendar mr-2"></i>&nbsp; <span class="gworks-label"></span>  <i class="fa fa-caret-down"></i>');
      $(this).find('.gworks-label').html(filterLabel);

      const ranges = {};
      let rangeTypes = (typeof $(this).attr('filter-date-types') === 'undefined') ? null : $(this).attr('filter-date-types').split(',');

      if (rangeTypes == null) {
        rangeTypes = ['All', 'Today', 'Yesterday', 'Last 7 Days', 'Last 30 Days', 'This Month', 'Last Month'];
      }

      for (const rt of rangeTypes) {
        if (rt.trim() === 'All') {
          ranges.All = [moment(), moment().add(1, 'days')];
        } else if (rt.trim() === 'Today') {
          ranges.Today = [moment(), moment()];
        } else if (rt.trim() === 'Yesterday') {
          ranges.Yesterday = [moment().subtract(1, 'days'), moment().subtract(1, 'days')];
        } else if (rt.trim() === 'Last 7 Days') {
          ranges['Last 7 Days'] = [moment().subtract(6, 'days'), moment()];
        } else if (rt.trim() === 'Last 30 Days') {
          ranges['Last 30 Days'] = [moment().subtract(29, 'days'), moment()];
        } else if (rt.trim() === 'This Month') {
          ranges['This Month'] = [moment().startOf('month'), moment().endOf('month')];
        } else if (rt.trim() === 'Last Month') {
          ranges['Last Month'] = [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')];
        }
      }

      const this_ = this;
      $(this).daterangepicker({
        startDate: moment(),
        endDate: moment().add(5, 'days'),
        opens: 'left',
        ranges: ranges,
        showCustomRangeLabel: true,
        autoUpdateInput: false
      }, function (momentStart, momentEnd, label) {
        if (label === 'All') {
          $(this_).removeAttr('filter-from').removeAttr('filter-to');
          $(this_).find('.gworks-label').html(filterLabel);
        } else {
          $(this_).attr('filter-from', momentStart.format('YYYY-MM-DD'));
          $(this_).attr('filter-to', momentEnd.format('YYYY-MM-DD'));
          $(this_).find('.gworks-label').html(momentStart.format('MM/DD/YY') + ' &raquo; ' + momentEnd.format('MM/DD/YY'));
        }
        dataCard.fetchData();
      });
    });
  },

  fetchParams: function (selector) {
    const data = {
      equals: {},
      range: {}
    };

    $(selector).find('.filter').each(function () {
      if ($(this).attr('filter-order-by') !== undefined && $(this).attr('filter-order-by') != null && $(this).attr('filter-order-by') !== '') {
        data.order = [$(this).attr('filter-order-by')];
      } else if ($(this).attr('filter-val') !== undefined && (!$(this).hasClass('rangefilter')) && $(this).attr('filter-val') != null && $(this).attr('filter-val') !== '') {
        const valEl = $(this).attr('filter-val').split(',');
        if (valEl.length === 1) {
          data.equals[$(this).attr('filter-name')] = valEl[0].trim();
        } else {
          for (let x = 0; x < valEl.length; x++) {
            valEl[x] = valEl[x].trim();
          }
          data.equals[$(this).attr('filter-name')] = valEl;
        }
      } else if ($(this).attr('filter-from') !== undefined && $(this).attr('filter-from') !== '' && $(this).attr('filter-to') !== undefined && $(this).attr('filter-to') !== '') {
        if ($(this).hasClass('rangefilter')) {
          data.range[$(this).attr('filter-name')] = {
            f: $(this).attr('filter-from'),
            t: $(this).attr('filter-to')
          };
        } else {
          if ($(this).attr('filter-date-type') === 'dateOnly') {
            data.range[$(this).attr('filter-name')] = {
              f: window.$gworks.core.renderDateLongTimeUtc($(this).attr('filter-from') + ' 00:00:00'),
              t: window.$gworks.core.renderDateLongTimeUtc($(this).attr('filter-to') + ' 23:59:59')
            };
          } else {
            data.range[$(this).attr('filter-name')] = {
              f: $(this).attr('filter-from') + ' 00:00:00',
              t: $(this).attr('filter-to') + ' 23:59:59'
            };
          }
        }
      }
    });

    let hubsFilter = data.equals['master-console-hubs-filter'];
    if (hubsFilter) {
      hubsFilter = Array.isArray(hubsFilter) ? hubsFilter : [hubsFilter];
      if (!hubsFilter.includes("")) {
        hubsFilter.map((hub) => data.equals[hub] = true );
      };
    }
    delete data.equals['master-console-hubs-filter'];

    const timezone = $('table').data('timezone');
    if (timezone) {
      data.timezone = timezone;
    }

    return data;
  }

};

},{}],9:[function(require,module,exports){
module.exports = {

  enable: function (scopeId = null) {
    if (scopeId == null) {
      $('button').each(function () {
        $(this).attr('disabled', false);
      });
    } else {
      $(scopeId).each(function () {
        $(this).find('button').each(function () {
          $(this).html($(this).attr('form-enable-text'));
          $(this).attr('disabled', false);
        });
      });
    }
  },

  disable: function (scopeId = null) {
    if (scopeId == null) {
      $('button').each(function () {
        $(this).attr('disabled', true);
      });
    } else {
      $(scopeId).each(function () {
        $(this).find('button').each(function () {
          $(this).attr('form-enable-text', $(this).html());

          if ($(this).attr('form-disable-text') !== '') {
            $(this).html($(this).attr('form-disable-text'));
          }

          $(this).attr('disabled', true);
        });
      });
    }
  }
}
;

},{}],10:[function(require,module,exports){
module.exports.do = function (scopeId, scanType = 'active') {
  scanType = scanType.toLowerCase();

  require('./type.telephone').show(scopeId);
  require('./type.sensitive').show(scopeId);

  if (typeof (tinymce) !== 'undefined') {
    tinymce.triggerSave();
  }

  const fields = {};
  $(scopeId).each(function () {
    $(this).find('input, textarea, select').each(function () {
      if (scanType === 'active' && $(this).is(':disabled')) {
        return;
      }

      const el = $(this)[0];
      if (typeof el.name === 'undefined' || el.name === '') {
      } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
        if (el.tagName === 'INPUT' && (el.type.toLowerCase() === 'checkbox' || el.type.toLowerCase() === 'radio')) {
          const typeBoolean = $(this).attr('value-type') !== 'undefined' && $(this).attr('value-type') === 'boolean';

          if (el.checked === true) {
            if (fields[el.name]) {
              fields[el.name] += ',' + (typeBoolean ? true : el.value.trim());
            } else {
              fields[el.name] = (typeBoolean ? true : el.value.trim());
            }
          } else if (typeof $(this).attr('value-unchecked') !== 'undefined') {
            fields[el.name] = typeBoolean ? false : $(this).attr('value-unchecked');
          }
        } else if (el.tagName === 'INPUT' && el.type.toLowerCase() === 'date') {
          fields[el.name] = (el.value === '') ? null : el.value;
        } else if (el.tagName === 'INPUT' && $(el).attr('form-type') === 'time') {
          const $container = $(el).closest('.form-group');
          const hours = Number($container.find('input[form-time="hour"]').val());
          const mins = Number($container.find('input[form-time="min"]').val());

          fields[el.name] = (hours * 60) + mins;
        } else if ($(el).attr('form-type') === 'currency') {
          fields[el.name] = Math.round((Number(el.value) * 100));
        } else if (el.tagName === 'INPUT' && el.type.toLowerCase() === 'number') {
          fields[el.name] = (el.value === '') ? null : Number(el.value);
        } else if (el.tagName === 'SELECT' && typeof $(this).attr('multiple') !== 'undefined') {
          fields[el.name] = $(this).val().join();
        } else if (el.tagName === 'SELECT' && $(this).attr('value-type') !== 'undefined' && $(this).attr('value-type') === 'number' && $(this).val() !== '') {
          fields[el.name] = Number(el.value);
        } else {
          fields[el.name] = el.value.trim();
        }
      }
    });
  });

  require('./type.telephone').hide(scopeId);
  require('./type.sensitive').hide(scopeId);
  return fields;
}
;

},{"./type.sensitive":20,"./type.telephone":21}],11:[function(require,module,exports){
module.exports.do = function (scopeId, data) {
  $(scopeId).each(function () {
    $(this).find('input, textarea, select').each(function () {
      const el = $(this)[0];

      if (typeof data[el.name] === 'undefined' || data[el.name] == null) {
      } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
        if (el.tagName === 'INPUT' && (el.type.toLowerCase() === 'checkbox' || el.type.toLowerCase() === 'radio')) {
          if (typeof data[el.name] === 'string') {
            const checkList = data[el.name].split(',');
            if (checkList.length) {
              for (const val of checkList) {
                if ((el.value === val || el.value === (val + ''))) {
                  el.checked = true;
                  break;
                }
              }
            }
          } else {
            const typeBoolean = $(this).attr('value-type') !== 'undefined' && $(this).attr('value-type') === 'boolean';

            if (typeBoolean) {
              el.checked = (data[el.name] || data[el.name] === 'true');
            } else {
              el.checked = (el.value === data[el.name] || el.value === (data[el.name] + ''));
            }
          }
        } else if (el.tagName === 'INPUT' && el.type.toLowerCase() === 'date') {
          if (data[el.name].indexOf('T') > 0) {
            el.value = data[el.name].substring(0, data[el.name].indexOf('T'));
          } else {
            el.value = data[el.name];
          }
        } else if (el.tagName === 'SELECT' && typeof $(this).attr('multiple') !== 'undefined' && !$(this).hasClass('gworks-evt-select-two')) {
          const selectEl = $(this);
          $.each(data[el.name].split(','), function (i, e) {
            selectEl.find(`option[value="${e}"]`).prop('selected', true);
          });
        } else if ($(el).attr('form-type') === 'time') {
          const $container = $(el).closest('.form-group');
          const mins = Number(data[el.name]);

          $container.find('input[form-time="hour"]').val(Math.floor(mins / 60));
          $container.find('input[form-time="min"]').val(mins % 60);
        } else if ($(el).attr('form-type') === 'currency') {
          el.value = window.$gworks.core.renderCurrency(data[el.name], true).substring(1).replace(',', '');
        } else if (el.type.toLowerCase() !== 'file') {
          el.value = data[el.name];
        }
      }
    });
  });
}
;

},{}],12:[function(require,module,exports){
const error = require('./error');

module.exports.do = function (scopeId) {
  if (typeof (tinymce) !== 'undefined') {
    tinymce.triggerSave();
  }

  let bValid = true;

  $(scopeId).each(function () {
    $(this).find('input, textarea, select').each(function () {
      const el = $(this)[0];
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') {
        if (($(this).is(':hidden') || $(this).is(':disabled')) && $(this).attr('form-type') !== 'time') {
          return;
        }

        if (el.type === 'checkbox') {
          if ($(this).attr('form-required') === 'true' && el.checked === false) {
            bValid = false;
            error.render($(this), $(this).attr('form-error-message'));
          }
        } else {
          if (el.type === 'date' && el.value.trim() !== '' && el.value.match(/\d{4}-\d{1,2}-\d{1,2}/)) {
            if (el.value !== '' && $(this).attr('min') !== undefined && new Date(el.value).getTime() < new Date($(this).attr('min')).getTime()) {
              bValid = false;
              const myCurrentDate = new Date($(this).attr('min'));
              const myPastDate = new Date(myCurrentDate);
              error.render($(this), `Must be after ${window.$gworks.core.renderDateShort(myPastDate.setDate(myPastDate.getDate() - 1))} `);
            } else if (el.value !== '' && $(this).attr('max') !== undefined && new Date(el.value).getTime() > new Date($(this).attr('max')).getTime()) {
              bValid = false;
              error.render($(this), `May not exceed ${window.$gworks.core.renderDateShort($(this).attr('max'))} `);
            }
          } else if (el.type === 'email' && el.value.trim() !== '') {
            const regex = /^([a-zA-Z0-9_.+-])+@(([a-zA-Z0-9-])+\.)+([a-zA-Z0-9]{2,4})+$/;
            if (el.value.trim() === '') {
              bValid = false;
              error.render($(this), $(this).attr('form-error-message'));
            } else if (!regex.test(el.value)) {
              bValid = false;
              error.render($(this), 'please enter a valid email');
            }
          } else if (el.type === 'number' && el.value.trim() !== '') {
            const v = Number(el.value);
            if ($(this).attr('form-min-val') !== '' && v < Number($(this).attr('form-min-val'))) {
              bValid = false;
              error.render($(this), `must be greater than ${$(this).attr('form-min-val')}`);
            } else if ($(this).attr('form-max-val') !== '' && v > Number($(this).attr('form-max-val'))) {
              bValid = false;
              error.render($(this), `must be less than ${$(this).attr('form-max-val')}`);
            }
          } else if (el.type === 'tel' && el.value.trim() !== '') {
            const v = el.value.replace(/[^0-9]+/g, '');
            if (v.length < 10) {
              bValid = false;
              error.render($(this), $(this).attr('form-error-message'));
            }
          } else if ($(el).attr('form-input-type') === 'zipcode') {
            if (el.value.length < Number($(el).attr('minlength'))) {
              bValid = false;
              error.render($(this), 'zipcode is invalid');
            } else if (el.value.includes('-') && el.value.indexOf('-') !== 5) {
              bValid = false;
              error.render($(this), 'zipcode is invalid');
            }
          } else if ($(this).attr('form-type') === 'time') {
            const $container = $(el).closest('.form-group');
            const hours = Number($container.find('input[form-time="hour"]').val());
            const mins = Number($container.find('input[form-time="min"]').val());
            if ($(this).attr('form-required') === 'true' && el.value.trim() === '' && (hours * 60) + mins === 0) {
              bValid = false;
              if ($(this).attr('form-error-message') === undefined) {
                $(this).attr('form-error-message', 'This field is required');
              }
              error.render($(this), $(this).attr('form-error-message'));
            } 
            else if ($(this).attr('form-day-validation') === 'true' && $container.css('display') !== 'none' && (((hours) < 0 || (mins) < 0) || (mins >= 60) || (hours > 24) || (hours === 24 && mins > 0) || (hours === 0 && mins === 0))) {
              bValid = false;
              error.render($(this),'Please enter a valid time unit');
            }
          }
          let errorType = (el.type === 'number') ? 'digits' : 'chars';
          if ($(this).attr('gworks-evt-error-type') === 'digit') { errorType = 'digits'; }
          if ($(this).attr('form-required') === 'true' && el.value.trim() === '' && $(this).attr('form-type') !== 'time') {
            bValid = false;
            if ($(this).attr('form-error-message') === undefined) {
              $(this).attr('form-error-message', 'This field is required');
            }
            error.render($(this), $(this).attr('form-error-message'));
          } else if (el.value !== '' && $(this).attr('form-min-length') !== '' && el.value.trim().length < Number($(this).attr('form-min-length'))) {
            bValid = false;
            error.render($(this), `must be at least ${$(this).attr('form-min-length')} or more ${errorType}`);
          } else if (el.value !== '' && $(this).attr('form-max-length') !== '' && el.value.trim().length > Number($(this).attr('form-max-length'))) {
            bValid = false;
            error.render($(this), `must be less than ${$(this).attr('form-max-length')} ${errorType}`);
          } else if (el.value !== '' && $(this).attr('form-exact-length') !== undefined && el.value.trim().length !== Number($(this).attr('form-exact-length'))) {
            bValid = false;
            error.render($(this), `must be ${$(this).attr('form-exact-length')} ${errorType}`);
          } else if (el.value !== '' && $(this).attr('form-pattern') !== undefined) {
            const pattern = new RegExp($(this).attr('form-pattern'));
            if(!pattern.test(el.value)){
              bValid = false;
              const patternMessage = $(this).attr('form-pattern-title') ?? 'Invalid Pattern';
              error.render($(this), patternMessage);
            }
          } 
          if(el.value !== '' && $(this).attr('form-max-digit-length-value') !== undefined){
            const digitsValue = el.value.replace(/[^0-9]/g,'');
            if(digitsValue.length > Number($(this).attr('form-max-digit-length-value'))){
              bValid = false;
              error.render($(this), `digits length must be less than ${$(this).attr('form-max-digit-length-value')}`);
            }
          } 
          if(el.value !== '' && $(this).attr('form-min-digit-length-value') !== undefined){
            const digitsValue = el.value.replace(/[^0-9]/g,'');
            if(digitsValue.length < Number($(this).attr('form-min-digit-length-value'))){
              bValid = false;
              error.render($(this), `digits length must be at least ${$(this).attr('form-min-digit-length-value')}`);
            }
          }

        }
      }
    });
  });

  return bValid;
}
;

},{"./error":13}],13:[function(require,module,exports){
module.exports = {

  clear: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('input, textarea, select').each(function () {
        $(this).removeClass('inputError');
        $(this).closest('.form-group').find('.gworks-evt-error').text('');
      });
    });
  },

  reset: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('input, textarea, select').each(function () {
        $(this).val('');
      });
    });
  },

  displayField: function (scopeId, formName, errMess) {
    const el = $(scopeId).find(`[name="${formName}"]`);
    this.render(el, errMess);
  },

  render: function (fieldEl, errMess) {
    $(fieldEl).addClass('inputError');

    const fieldName = $(fieldEl).attr('name');
    const errField = $(fieldEl).closest('.form-group').find('.gworks-evt-error');

    if (errField.length !== 0) {
      errField.text(errMess);

      if (typeof fieldName !== 'undefined') {
        errField.addClass(fieldName.replace('.', '_'));
      }
    }
  }

}
;

},{}],14:[function(require,module,exports){
module.exports = {

  init: function (scopeId) {
    require('./type.zipcode').init(scopeId);
    require('./type.lookup').init(scopeId);
    require('./type.date').init(scopeId);
    require('./type.charcount').init(scopeId);
    require('./type.telephone').init(scopeId);
    require('./type.us.state').init(scopeId);
    require('./type.sensitive').init(scopeId);
    return this;
  },

  enableButtons: function (scopeId = null) {
    require('./buttons').enable(scopeId);
    return this;
  },

  disableButtons: function (scopeId = null) {
    require('./buttons').disable(scopeId);
    return this;
  },

  reset: function (scopeId) {
    require('./error').reset(scopeId);
    return this;
  },

  clear: function (scopeId) {
    require('./error').clear(scopeId);
    return this;
  },

  displayFieldError: function (scopeId, formName, errMess) {
    require('./error').displayField(scopeId, formName, errMess);
    return this;
  },

  validate: function (scopeId) {
    return require('./data.validate').do(scopeId);
  },

  setData: function (scopeId, data) {
    require('./data.set').do(scopeId, data);
    return this;
  },

  getData: function (scopeId, scanType) {
    return require('./data.get').do(scopeId, scanType);
  },

  getMentions: function () {
    return require('./mentions');
  },

  textarea2RichEditor: function (selector, height, removeobj) {
    require('./richtext').textarea2RichEditor(selector, height, removeobj);
  },

  setRichEditorValue: function (editorVal, editorId) {
    require('./richtext').setRichEditorValue(editorVal, editorId);
  },

  getRichEditorValue (editorId) {
    return require('./richtext').getRichEditorValue(editorId);
  }

};

},{"./buttons":9,"./data.get":10,"./data.set":11,"./data.validate":12,"./error":13,"./mentions":15,"./richtext":16,"./type.charcount":17,"./type.date":18,"./type.lookup":19,"./type.sensitive":20,"./type.telephone":21,"./type.us.state":22,"./type.zipcode":23}],15:[function(require,module,exports){
module.exports = {
  init: function (selector, data) {
    const thisInst = this;
    $(selector).data('mentions', data);

    $(selector).each(function () {
      thisInst.renderMention($(this));
    });
  },

  renderMention: function (selector) {
    $(selector).mentionsInput({
      source: this.getStoredData(selector),
      suffix: ' '
    });
  },

  getStoredData: function (selector) {
    return $(selector).data('mentions');
  },

  getMentionValue: function (selector) {
    const data = $(selector).mentionsInput('getValue');
    if (typeof data === 'string') {
      return data;
    } else {
      return '';
    }
  },

  getMentionData: function (selector) {
    return $(selector).mentionsInput('getRawValue');
  },

  covertDataToLink: function (data, cbFn) {
    return data.replace(/@\[([^\]]+)\]\(([^ )]+)\)/g, function (val, name, id) {
      return cbFn(val, name, id);
    });
  }
};

},{}],16:[function(require,module,exports){
module.exports = {
  textarea2RichEditor: function (selector, height, removeobj) {
    if (removeobj) {
      if (tinymce.get(removeobj)) {
        tinymce.get(removeobj).remove();
      }
    }
    const activePlugins = [
      'advlist autolink lists link charmap print preview anchor',
      'searchreplace visualblocks code',
      'insertdatetime table paste code help wordcount', 'media'
    ];

    if (!$(selector).hasClass('gworks-evt-richeditor-no-media')) {
      $(selector).closest('div').append('<div class="btns-block"><button type="button" gworks-evt-images-only="true" class="btn btn-outline-secondary gworks-editor-add-image">Insert Image</button><button type="button" gworks-evt-images-only="true" class="btn btn-outline-secondary gworks-editor-add-files">Insert File</button><button type="button" gworks-evt-images-only="true" class="btn btn-outline-secondary gworks-editor-add-page">Insert Page</button></div>');

      $(selector).closest('div').find('.gworks-editor-add-image').click(function () {
        window.$gworks.plugin.get('cms').getMediaLibraryPopup().showPopup({
          selector: '#gworks-evt-custom-standardModal',
          contentBlock: 'medialibrary-custom-popup-block',
          filter: 'images',
          fnOnInsertHtml: function (html) {
            tinymce.activeEditor.execCommand('mceInsertContent', false, html);
          }
        });
      });

      $(selector).closest('div').find('.gworks-editor-add-files').click(function () {
        window.$gworks.plugin.get('cms').getMediaLibraryPopup().showPopup({
          selector: '#gworks-evt-custom-standardModal',
          contentBlock: 'medialibrary-custom-popup-block',
          filter: 'nonimages',
          fnOnInsertHtml: function (html) {
            tinymce.activeEditor.execCommand('mceInsertContent', false, html);
          }
        });
      });
    } else {
      if ($(selector).closest('div').find('.gworks-editor-add-page').length === 0 && !$(selector).hasClass('gworks-evt-richeditor-no-pages')) {
        $(selector).closest('div').append('<div class="btns-block"> <button type="button" gworks-evt-images-only="true" class="btn btn-outline-secondary gworks-editor-add-page">Insert Page</button></div>');
      }
    }
    $(selector).closest('div').find('.gworks-editor-add-page').click(function () {
      let pagelink = '';
      if ($(selector).hasClass('gworks-evt-richeditor-full-link')) {
        pagelink = 'full';
      }
      window.$gworks.plugin.get('cms').getMediaLibraryPopup().showPopup({
        pageLink: pagelink,
        selector: '#gworks-evt-custom-standardModal',
        contentBlock: 'medialibrary-custom-popup-block',
        filter: 'pages',
        fnOnInsertHtml: function (html) {
          tinymce.activeEditor.execCommand('mceInsertContent', false, html);
        }
      });
    });
    height = height || 300;

    tinymce.init({
      selector: selector,
      height: height,
      elementpath: false,
      media_dimensions: false,
      media_filter_html: false,
      media_poster: false,
      media_live_embeds: false,
      convert_urls: false,
      menubar: 'edit view insert format table tc help',

      plugins: activePlugins,
      toolbar: 'undo redo | formatselect | ' +
        'bold italic backcolor | alignleft aligncenter ' +
        'alignright alignjustify | bullist numlist outdent indent | ' +
        'removeformat' + 'medialibrary' + 'pages' + 'media'
    });

    $(document).on('focusin', function (e) {
      if ($(e.target).closest('.tox').length) {
        $('#gworks-evt-standardModal').removeAttr('tabindex');
        e.stopImmediatePropagation();
      }
    });

    $(document).on('focusin', function (e) {
      if ($(e.target).closest('.tox-tinymce-aux, .moxman-window, .tam-assetmanager-root, .tox-dialog').length) {
        $('.tox-dialog').css('z-index', '2003');
        e.stopImmediatePropagation();
      }
    });
  },

  setRichEditorValue: function (editorVal, editorId) {
    if (editorId) {
      tinymce.get(editorId).setContent(editorVal);
    } else {
      tinymce.activeEditor.setContent(editorVal);
    }
  },

  getRichEditorValue (editorId) {
    if (editorId) {
      return tinymce.get(editorId).getContent();
    } else {
      return null;
    }
  }
}
;

},{}],17:[function(require,module,exports){
module.exports.init = function (scopeId) {
  $(scopeId).find('[form-show-char-count="true"]').each(function () {
    const maxCount = $(this).attr('form-max-length') ? $(this).attr('form-max-length') : 120;
    const charCount = Number(maxCount) - $(this).val().length;

    $(this).parent().addClass('position-relative');
    $(this).parent().find('.gworks-remaining-count-block').remove();
    $(this).before(`<div class="gworks-remaining-count-block remainingChar"><span class="gworks-remaining-count">${charCount}</span> characters remaining</div>`);
  });

  $(scopeId).find('[form-show-char-count="true"]').keyup(onKeyUp);
}
;


function onKeyUp () {
  const charCount = $(this).attr('form-max-length') ? Number($(this).attr('form-max-length')) : 120;
  if ($(this).val().length > charCount) {
    $(this).text($(this).val().substr(0, charCount));
  }
  $(this).prev().find('.gworks-remaining-count').html(charCount - $(this).val().length);
}

},{}],18:[function(require,module,exports){
module.exports.init = function (scopeId) {
  const today = new Date().toISOString().split('T')[0];

  $(scopeId).find('[form-date-future="true"]').each(function () {
    $(this).attr('min', today);
  });

  $(scopeId).find('[form-date-past="true"]').each(function () {
    $(this).attr('max', today);
  });
}
;

},{}],19:[function(require,module,exports){
module.exports.init = function (scopeId) {
  $(scopeId).each(function () {
    $(this).find('.gworks-data-lookup-refdata').each(function (e) {
      if ($(this).html().trim() === '') {
        const refScope = $(this).attr('gworks-ref-scope');
        if (refScope !== '') {
          const refData = window.$gworks.lookup.getRef(refScope);
          let optionList = '';
          if ($(this).hasClass('gworks-ref-allow-zero')) {
            optionList += "<option value='0'></option>";
          } else if ($(this).hasClass('gworks-ref-allow-blank')) {
            const blankVal = (typeof $(this).attr('gworks-ref-blank-value') === 'undefined') ? '' : $(this).attr('gworks-ref-blank-value');
            const selected = (blankVal !== '') ? 'selected=selected' : '';
            const blankLabel = (typeof $(this).attr('gworks-ref-blank-label') === 'undefined') ? '' : $(this).attr('gworks-ref-blank-label');
            optionList += `<option value='${blankVal}' ${selected}>${blankLabel}</option>`;
          }

          let filter = $(this).attr('gworks-ref-filter');
          if (typeof filter === 'undefined' || filter.trim() === '') {
            filter = [];
          } else {
            filter = filter.split(',');
            for (let x = 0; x < filter.length; x++) {
              filter[x] = Number(filter[x].trim());
            }
          }

          if (refData != null) {
            const valSet = $(this).attr('value') !== '' ? Number($(this).attr('value')) : 0;
            for (const ref of refData) {
              ref.label = ref.label === 'Payrix' ? 'gWorks Payments' : ref.label;
              if (filter.length === 0 || filter.indexOf(ref.id) !== -1) {
                if ($(this).hasClass('gworks-data-lookup-refdata-value-only')) {
                  const selected = (valSet === ref.label) ? 'selected=selected' : '';
                  optionList += `<option value='${ref.label}' ${selected}>${ref.label}</option>`;
                } else if ($(this).hasClass('gworks-data-lookup-refdata-value-with-class')) {
                  const selected = (valSet === ref.label) ? 'selected=selected' : '';
                  optionList += `<option class='${ref.label.replace(/\s/g, '').toLowerCase()}' value='${ref.label}' ${selected}>${ref.label}</option>`;
                } else {
                  const selected = (valSet === ref.id) ? 'selected=selected' : '';
                  optionList += `<option value='${ref.id}' ${selected}>${ref.label}</option>`;
                }
              }
            }
          }
          $(this).html(optionList);
        }
      }
    });
  });
}
;

},{}],20:[function(require,module,exports){
module.exports = {

  init: function (scopeId) {
    $(scopeId).off('blur').on('blur', '.gworks-evt-sensitive', onBlur);
    $(scopeId).off('focus').on('focus', '.gworks-evt-sensitive', onFocus);
    $(scopeId).off('keyup').on('keyup', '.gworks-evt-sensitive', onKeyUp);
  },

  show: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('.gworks-evt-sensitive').each(function (e) {
        const ssvVal = $(this).attr('gworks-evt-ssv');
        if (ssvVal !== '') {
          $(this).val(ssvVal);
        }
      });
    });
  },

  hide: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('.gworks-evt-sensitive').each(function (e) {
        $(this).val($(this).val().replace(/./gi, '*'));
      });
    });
  }

}
;


function onBlur (e) {
  e.stopImmediatePropagation();
  if ($(this).attr('field-type') === 'removed') {
    const oldData = $(this).data('old-data');
    $(this).attr('field-type', 'old');
    $(this).val(oldData);
    $(this).attr('gworks-evt-ssv', oldData);
  }
}


function onFocus (e) {
  e.stopImmediatePropagation();
  if ($(this).attr('field-type') === 'old' && $(this).attr('field-type') !== 'new') {
    $(this).data('old-data', $(this).attr('gworks-evt-ssv'));
    $(this).attr('field-type', 'removed');
    $(this).val('');
    $(this).attr('gworks-evt-ssv', '');
  } else {
    $(this).val($(this).val().replace(/./gi, '*'));
  }
}


function onKeyUp (e) {
  e.stopImmediatePropagation();
  $(this).attr('field-type', 'new');

  const ignorekeys = [16, 17, 20, 37, 38, 39, 40];
  if (ignorekeys.indexOf(e.which) >= 0) {
    return false;
  }

  $(this).prop('disabled', true);
  const fieldval = $(this).val();
  let userchar = '';
  let existval = $(this).attr('gworks-evt-ssv');

  if (typeof existval === 'undefined') {
    existval = '';
  }

  if (fieldval.length < existval.length) {
    existval = existval.substr(0, fieldval.length);
  } else {
    let newCharPos = 0;
    for (let i = 0; i < fieldval.length; i++) {
      if (fieldval.charAt(i) !== '*') {
        newCharPos = i;
        userchar = fieldval.charAt(i);
        break;
      }
    }

    if (!fieldval.includes('*')) {
      existval = fieldval;
    } else if (newCharPos < existval.length) {
      existval = existval.substr(0, newCharPos) + userchar + existval.substr(newCharPos, existval.length);
    } else {
      existval = existval + userchar;
    }
  }

  $(this).attr('gworks-evt-ssv', existval);
  const maskStr = $(this).attr('gworks-evt-ssv').replace(/./gi, '*');

  $(this).val(maskStr);
  $(this).prop('disabled', false);
  $(this).focus();
}

},{}],21:[function(require,module,exports){
module.exports = {
  init: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('.gworks-evt-tel').each(function () {
        $(this).off('focus').on('focus', onFocus);
        $(this).off('blur').on('blur', onBlur);
        $(this).val(window.$gworks.core.renderPhone($(this).val()));
      });
    });
  },

  show: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('.gworks-evt-tel').each(function (e) {
        $(this).attr('type', 'tel');
        const inpVal = $(this).val().replace(/[^0-9]+/g, '');
        if (inpVal !== '') {
          $(this).val(`+1${inpVal}`);
        }
      });
    });
  },

  hide: function (scopeId) {
    $(scopeId).each(function () {
      $(this).find('.gworks-evt-tel').each(function (e) {
        $(this).attr('type', 'tel');
        const origVal = $(this).val();
        if (origVal !== '') {
          $(this).val(window.$gworks.core.renderPhone(origVal));
        }
      });
    });
  }
}
;


function onFocus () {
  const inpVal = $(this).val().replace(/[^0-9]+/g, '');
  if (inpVal !== '') {
    $(this).val(inpVal);
  }
}


function onBlur () {
  const origVal = $(this).val();
  if (origVal !== '') {
    $(this).val(window.$gworks.core.renderPhone(origVal));
  }
}

},{}],22:[function(require,module,exports){
module.exports.init = function (scopeId) {
  let optionList = null;

  $(scopeId).each(function () {
    $(this).find('.gworks-evt-data-usstates').each(function (e) {
      if ($(this).html() === '') {
        optionList = (optionList == null) ? getOptionList() : optionList;
        $(this).html(optionList);
      }
    });
  });
}
;

function getOptionList () {
  let optionList = '';
  const usstate = window.$gworks.lookup.getUsStates();
  for (const ref of usstate) {
    if (optionList === '') {
      optionList += `<option value='${ref.short}'>${ref.long}</option>`;
    } else {
      optionList += `<option value='${ref.short}'>${ref.short}</option>`;
    }
  }

  return optionList;
}

},{}],23:[function(require,module,exports){
module.exports.init = function (scopeId) {
  $(scopeId).each(function () {
    $(this).off('keypress').on('keypress', '.gworks-evt-zipcode', onKeyPress);
    $(this).off('focus').on('focus', '.gworks-evt-zipcode', onFocus);
    $(this).off('blur').on('blur', '.gworks-evt-zipcode', onBlur);
  });
}
;


function onKeyPress (evt) {
  if ($(this).val().length >= 5 && !$(this).val().includes('-') && evt.charCode === 45) {
    $(this).attr('maxlength', 10);
    return true;
  } else if (!$(this).val().includes('-')) {
    $(this).attr('maxlength', 9);
  }

  if ((evt.charCode < 48 || evt.charCode > 57)) {
    return false;
  }
}


function onFocus () {
  const inpVal = $(this).val().replace(/[^0-9]+/g, '');
  if (inpVal !== '') {
    $(this).val(inpVal);
  }
}


function onBlur () {
  let inputVal = $(this).val();
  if (inputVal.endsWith('-') || inputVal.startsWith('-')) {
    inputVal = inputVal.replace(/-/, '');
  }
  if (inputVal.length < Number($(this).attr('minlength')) || inputVal.length > Number($(this).attr('maxlength'))) {
    $(this).siblings('.gworks-evt-error').html('zipcode is invalid');
  } else {
    $(this).siblings('.gworks-evt-error').html('');
    if (!$(this).val().includes('-')) {
      $(this).val(window.$gworks.core.renderZipCode(inputVal));
    } else {
      $(this).val(inputVal);
    }
  }
}

},{}],24:[function(require,module,exports){
module.exports = class GWorksCoreData {
  setPAMUrl (pamUrl) {
    this.pamUrl = pamUrl;
  }

  gePAMUrl () {
    return 'pamUrl' in this ? this.pamUrl : null;
  }

  renderDateShort (dt) {
    return dt != null ? moment(dt).format('L') : '';
  }

   renderMonthName (dt) {
    return dt != null ? moment(dt).format('MMMM') : '';
  }

  renderDateLong (dt) {
    return dt != null ? moment(dt).format('ll') : '';
  }

  renderDateLongTime (dt) {
    return dt != null ? moment(dt).format('ll LT') : '';
  }

  renderDateLongTimeSeconds (dt) {
    return dt != null ? moment(dt).format('ll LTS') : '';
  }

  renderTime (dt) {
    return dt != null ? moment(dt).format('LT') : '';
  }

  renderDateShortUtc (dt) {
    return dt != null ? moment(dt).utc().format('L') : '';
  }

  renderDateLongUtc (dt) {
    return dt != null ? moment(dt).utc().format('ll') : '';
  }

  renderDateLongTimeUtc (dt) {
    return dt != null ? moment(dt).utc().format('ll LT') : '';
  }

  renderDateLongTimeSecondsUtc (dt) {
    return dt != null ? moment(dt).utc().format('ll LTS') : '';
  }

  renderTimeUtc (dt) {
    return dt != null ? moment(dt).utc().format('LT') : '';
  }

  renderStorage (amt) {
    if (amt === null || amt === '') {
      return '';
    }

    amt = Number(amt);
    if (amt < 1000) {
      return amt + ' KB';
    } else if (amt < 1000000) {
      return (amt / 1000).toFixed(2) + ' MB';
    } else {
      return (amt / 10000000).toFixed(2) + ' GB';
    }
  }

  renderPercentage (amt, flag) {
    if (amt === '-') {
      return '-%';
    } else if (flag === true) {
      amt = (amt * 100).toFixed(2);
      return `${amt.toLocaleString('en-US', { maximumFractionDigits: 2 })}%`;
    } else {
      amt = Math.round(amt * 100);
      return `${amt.toLocaleString('en-US', { maximumFractionDigits: 0 })}%`;
    }
  }

  renderCurrency (amtCents, flag) {
    if (amtCents == null) {
      return '$-';
    }

    const amtDollars = Number(Math.round(Number(amtCents)) / 100).toFixed(2);
    if (flag === true) {
      return `$${Number(amtDollars).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    } else {
      return `$${Number(amtDollars).toLocaleString('en', { maximumFractionDigits: 0 })}`;
    }
  }

  renderCurrencyWithoutDollar (amtCents, flag) {
    if (amtCents == null) {
      return '-';
    }

    const amtDollars = Number(Math.round(Number(amtCents)) / 100).toFixed(2);
    if (flag === true) {
      return Number(amtDollars).toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else {
      return Number(amtDollars).toLocaleString('en', { maximumFractionDigits: 0 });
    }
  }

  renderPhone (data) {
    if (typeof data === 'undefined' || data == null || data === '') {
      return '';
    }

    data = data.replace(/[^0-9]+/g, '');
    if (data.length === 11) {
      data = data.substring(1);
    }

    if (data.length === 10) {
      return data.replace(/(\d{3})(\d{3})(\d{4})/, '($1) $2-$3');
    } else {
      return data;
    }
  }

  renderZipCode (data) {
    if (typeof data === 'undefined' || data == null || data === '') {
      return '';
    }

    const startVal = data.substring(0, 5);
    const endVal = data.substring(5, data.length);

    if (data.length > 5) {
      return `${startVal}-${endVal}`;
    } else {
      return startVal;
    }
  }

  renderAddress2Line (add1, add2, city, state, zip) {
    const firstLine = [];
    if (typeof add1 !== 'undefined' && add1 != null && add1 !== '') {
      firstLine.push(add1);
    }
    if (typeof add2 !== 'undefined' && add2 != null && add2 !== '') {
      firstLine.push(add2);
    }

    let html = '';
    if (firstLine.length > 0) {
      html = `<div class="small">${firstLine.join(', ')}</div>`;
    }

    const secLine = [];
    if (typeof city !== 'undefined' && city != null && city !== '') {
      secLine.push(city);
    }
    if (typeof state !== 'undefined' && state != null && state !== '') {
      secLine.push(state.toUpperCase());
    }
    if (typeof zip !== 'undefined' && zip != null && zip !== '') {
      secLine.push(zip);
    }
    if (secLine.length > 0) {
      html += `<div class="small">${secLine.join(', ')}</div>`;
    }

    return html;
  }

  renderPersonCreateMod (person, dt) {
    if (typeof dt !== 'undefined' && dt != null && dt !== '') {
      person = (typeof person === 'undefined') ? '' : person;
      return `<div class="small">${person}</div><div class="small">${window.$gworks.core.renderDateShort(dt)}</div>`;
    } else {
      return '';
    }
  }

  removeScope (data) {
    const nd = {};
    for (const key in data) {
      if (key.indexOf('.') > 0) {
        nd[key.substring(key.indexOf('.') + 1)] = data[key];
      } else {
        nd[key] = data[key];
      }
    }
    return nd;
  }

  flattenScope (data) {
    const nd = {};
    for (const key in data) {
      if (key.indexOf('.') > 0) {
        const scope = key.substring(0, key.indexOf('.'));
        if (typeof nd[scope] === 'undefined') {
          nd[scope] = {};
        }
        nd[scope][key.substring(key.indexOf('.') + 1)] = data[key];
      } else {
        nd[key] = data[key];
      }
    }
    return nd;
  }

  minutesToDhm (mins, maxDayMins = 480) {
    if (maxDayMins === 0) {
      return;
    }
    mins = Number(mins);
    const d = Math.floor(Math.abs(mins / maxDayMins));
    const h = Math.floor(Math.abs(mins % maxDayMins / 60));
    const m = Math.floor(Math.abs(mins % 60));

    return (mins < 0 ? '(' : '') + (d > 0 ? d + 'd ' : '') + (h > 0 ? h + 'h ' : '') + m + 'm' + (mins < 0 ? ')' : '');
  }

  minutesToHm (mins) {
    mins = Number(mins);
    const h = Math.floor(Math.abs(mins / 60));
    const m = Math.floor(Math.abs(mins % 60));

    return (mins < 0 ? '(' : '') + (h > 0 ? h + 'h ' : '') + m + 'm' + (mins < 0 ? ')' : '');
  }
};

},{}],25:[function(require,module,exports){
class GWorksCore extends require('./gworks.core.modal') {
  appendTitle (title) {
    document.title = title + ' - ' + document.title;
    $('.gworks-evt-pagetitle').html(`<span class='maintitle'>${$('.gworks-evt-pagetitle').html()}</span> - <span class='subtitle'>${title}</span>`);
  }

  updateSubTitle (title) {
    if ($('.subtitle').length === 0) {
      $('.gworks-evt-pagetitle').html(`<span class='maintitle'>${$('.gworks-evt-pagetitle').html()}</span> - <span class='subtitle'></span>`);
    }
    $('.subtitle').html(title);
  }

  setTitle (title) {
    document.title = title;
    $('.gworks-evt-pagetitle').html(title);
  }

  isCityPortal () {
    return 'city' in window.$gworks;
  }

  getFAMSyncVersion () {
    return this.isUserLoggedIn() ? window.$gworks.authUser.sv : -1;
  }

  isFAMEnabled () {
    return this.isUserLoggedIn()
      ? window.$gworks.authUser.fam
      : window.$gworks.lookup.getCityFeatures().indexOf('D') !== -1;
  }

  isSupportUser () {
    return this.isUserLoggedIn() ? window.$gworks.authUser.support : false;
  }

  isPAMEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('A') !== -1;
  }

  isFrontDeskEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('1') !== -1;
  }

  isUtilityBillingEnabled() {
    return window.$gworks.lookup.getCityFeatures().indexOf('2') !== -1;
  }

  isUtilityBillingDemoEnabled() {
    return window.$gworks.lookup.getCityFeatures().indexOf('E') !== -1;
  }

  isInQaEnabled() {
    return window.$gworks.lookup.getCityFeatures().indexOf('4') !== -1;
  }

  isPluginFormsEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('F') !== -1;
  }

  isPluginMessagingEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('M') !== -1 || window.$gworks.lookup.getCityFeatures().indexOf('W') !== -1;
  }

  isPluginTxtEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('T') !== -1;
  }

  isPluginCMSEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('W') !== -1;
  }

  isWebsiteActivated () {
    return window.$gworks.lookup.getCityFeatures().indexOf('Q') !== -1;
  }

  isPlugin311Enabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('3') !== -1;
    }

  isPluginPermitsEnabled() {
    return window.$gworks.lookup.getCityFeatures().indexOf('9') !== -1 && window.$gworks.lookup.getCityFeatures().indexOf('O') !== -1;
  }

  isPluginUtilitiesEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('U') !== -1;
  }

  isPluginPaymentsEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('P') !== -1;
  }

  isPluginReportsEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('R') !== -1;
  }

  isPluginTimeTracker () {
    return window.$gworks.lookup.getCityFeatures().indexOf('N') !== -1;
  }

  isPluginPayroll () {
    return window.$gworks.lookup.getCityFeatures().indexOf('B') !== -1;
  }

  isPluginPayrollDemo () {
    return window.$gworks.lookup.getCityFeatures().indexOf('V') !== -1;
  }

  isPluginCitizenPortal () {
    return window.$gworks.lookup.getCityFeatures().indexOf('C') !== -1;
  }

  isPublicNoticesEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('5') !== -1;
  }

    isAgendasMinutesEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('6') !== -1;
  }

  isFinanceHubEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('7') !== -1;
  }

  isFinanceLiteEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('Y') !== -1;
  }

  licenseExpiration() {
    return window.$gworks.lookup.getCityFeatures().indexOf('L') !== -1;
  }

  isOpsHubEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('9') !== -1;
  }

  isMapsHubEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('8') !== -1;
  }

  isGuestPaymentsEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('G') !== -1;
  }

  isCemeteryEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('Z') !== -1;
  }

  isCourtEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('H') !== -1;
  }

  isAutoPayEnabled () {
    return window.$gworks.lookup.getCityFeatures().indexOf('S') !== -1;
  }

  getUserId () {
    return this.isUserLoggedIn() ? window.$gworks.authUser.pId : -1;
  }

  getUserDisplayName () {
    return this.isUserLoggedIn() ? window.$gworks.authUser.pName : null;
  }

  getCityDisplayName () {
    return window.$gworks.lookup.getCityName();
  }

  getCityCode () {
    return this.isUserLoggedIn() ? window.$gworks.authUser.cId : window.$gworks.lookup.getCityCode();
  }

  getMediaFileUrl (filename) {
    return `${this.getFileUrl()}/media/${filename}`;
  }

  getFileUrl (filename) {
    return `${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}`;
  }

  onAuthTokenExpire () {
    window.location = '/';
  }

  isUserLoggedIn () {
    return window.$gworks.api.isUserLoggedIn();
  }

  doLogout () {
    window.$gworks.api.oauth.doLogout();
  }

  onSuccess (message, options) {
    toastr.clear();
    toastr.success(message, '', options);
    return this;
  }

  onWarning (message, options) {
    if (typeof message === 'object' && 'responseText' in message) {
      message = message.responseText;
    } else if (typeof message === 'object' && 'message' in message) {
      message = message.message;
    } else if (typeof message === 'object' && 'responseMessages' in message && message.responseMessages.length != 0) {
      message = message.responseMessages.map(m => m.description).join(' : ')
    }
    message = this.__translateMessage(message);
    options = options || {};
    options.timeOut = 5000;
    toastr.clear();
    toastr.warning(message, '', options);
    return this;
  }

  onError (message, options) {
    if (typeof message === 'object' && 'responseText' in message) {
      message = message.responseText;
    } else if (typeof message === 'object' && 'message' in message) {
      message = message.message;
    } else if (typeof message === 'object' && 'responseMessages' in message && message.responseMessages.length != 0) {
      message = message.responseMessages.map(m => m.description).join(' : ')
    }
    message = this.__translateMessage(message);
    options = options || {};
    if (!("timeOut" in options)) {
      options.timeOut = 8000;
    }
    toastr.clear();
    toastr.error(message, '', options);
    return this;
  }

  onDisplay (message, options) {
    if (typeof message === 'undefined' || message === null) {
      toastr.clear();
    } else {
      options = options || {
        progressBar: false
      };
      toastr.info(message.trim(), '', options);
    }
    return this;
    }

  __translateMessage (message) {
    if (message.indexOf('violates foreign key constraint') !== -1) {
      if (message.indexOf('person_email')) {
        message = 'You cannot remove this email, as it is required, by the login';
      } else {
        message = 'You cannot delete this element as it is relied on by another area';
      }
    } else if (message.indexOf('violates unique constraint') !== -1) {
      if (message.indexOf('person_email')) {
        message = 'this email is already in use';
      } else {
        message = 'duplicate value';
      }
    } else if (message.indexOf('already exists') !== -1) {
      message = message.substring(message.indexOf('=') + 1);
      message = message.indexOf(',') !== -1 ? (message.substring(1, message.indexOf(',')) + message.substring(message.indexOf(')') + 1)) : message;
    }
    return message;
  }

  getLicense () {
    return require('./license');
  }

  getMap () {
    return require('./map');
  }

  loadingOn () {
    $('.gworks-evt-fp-loader').removeClass('d-none').addClass('d-block');
  }

  loadingOff () {
    $('.gworks-evt-fp-loader').removeClass('d-block').addClass('d-none');
  }

  getLoadingHtml () {
    return '<div class="gworks-evt-formDataLoader formDataLoader mt-2" style="margin: 20px;">Loading <i class="fa fa-spin fa-spinner-third" aria-hidden="true"></i></div>';
  }

  setToolTip (selector) {
    $(selector).find('.gworks-tooltip').tooltip();
    }



  reWriteUrl (query, isReplace) {
    let uri = window.location.href;
    if (isReplace) {
      if (query.startsWith('?')) {
        uri = uri.replace(query, '');
      } else if (uri.indexOf(query) > 0) {
        const regExp = new RegExp(query);
        uri = uri.replace(regExp, '');
      }
    } else if (uri.indexOf('?') > 0) {
      uri = uri.substring(0, uri.indexOf('?') + 1) + query;
    } else {
      uri = `${uri}?${query}`;
    }

    if (window.location.href !== uri) {
      window.history.replaceState('', '', uri);
    }
  }
}


window.$gworks = window.$gworks || {};
window.$gworks.plugin = require('./plugin');
window.$gworks.form = require('./form/form');

window.$gworks.display = require('./display');
window.$gworks.liveshow = require('./liveshow');
window.$gworks.datacard = require('./datacard');
window.$gworks.datatable = require('./datatable');
window.$gworks.calendar = require('./calendar');
window.$gworks.cityuser = require('./cityuser');
window.$gworks.filter = require('./filter');

const ApiClass = require('./api');
window.$gworks.api = new ApiClass(window.configData.apiEndPoint);
window.$gworks.externalApi = new ApiClass(window.configData.externalApiEndpoint);
window.$gworks.ubmaxLambdaApi = new ApiClass(window.configData.ubmaxLambdaApiEndpoint)
window.$gworks.simpleCityLambdaApi = new ApiClass(window.configData.simpleCityLambdaApiEndpoint)
window.$gworks.lookup = require('./lookup');
window.$gworks.core = new GWorksCore();

async function getOpsFlags() {

    let ops_enabled = false;
    await window.$gworks.api.getSecure({
        uri: `/core/secure/utils/city/${window.$gworks.core.getCityCode()}`,
        fnSuccess: function (data) {
            let opsEnabled = data["city_license.ops_fl"];
            let opsFullEnabled = data["city_license.ops_full"]
            console.log(opsEnabled, opsFullEnabled);
            if (opsEnabled && opsFullEnabled) ops_enabled = true
        },
        fnError: function (data) {
            window.$gworks.core.onWarning(data);
        }
    });
    console.log(ops_enabled);
    return ops_enabled;
}

},{"./api":2,"./calendar":3,"./cityuser":4,"./datacard":5,"./datatable":6,"./display":7,"./filter":8,"./form/form":14,"./gworks.core.modal":26,"./license":28,"./liveshow":29,"./lookup":30,"./map":31,"./plugin":34}],26:[function(require,module,exports){
module.exports = class GWorksCorePage extends require('./gworks.core.page') {
  constructor() {
    super();
    this.stdModal = null;
  }

  confirm(options) {
    options.title = options.title || 'Are you sure?';
    const iconHtml =
      'iconHtml' in options && options.iconHtml != null
        ? options.iconHtml
        : '<i class="fal fa-times-circle ficon mt-3" aria-hidden="true"></i>';
    this.standardModal().open({
      title: '',
      btnCancelShow: 'btnCancelShow' in options ? options.btnCancelShow : true,
      btnCancelLabel: options.btnCancelLabel || 'Cancel',
      btnSubmitLabel: options.btnConfirmLabel || 'Confirm',
      content: `<div class="confirmationModal">
                  ${iconHtml}
                  <h4 class="modal-title noLine my-3">${options.title}</h4>
                  <p>${options.content}</p>
                </div>`,
      fnOnSubmit: options.fnConfirm || ''
    });

    $('#gworks-evt-standardModal').addClass('modal-confirmation');
    $('#gworks-evt-standardModal .modal-footer .btn-dark').removeClass('btn-dark');
  }

  confirmDelete(options) {
    options.title = options.title || 'Are you sure?';
    this.standardModal().open({
      title: '',
      btnCancelShow: 'btnCancelShow' in options ? options.btnCancelShow : true,
      btnCancelLabel: options.btnCancelLabel || 'Cancel',
      btnSubmitLabel: options.btnConfirmLabel || 'Delete',
      content: `<div class="confirmationModal">
                  <i class="fal fa-times-circle ficon text-danger mt-3" aria-hidden="true"></i>
                  <h4 class="modal-title noLine my-3">${options.title}</h4>
                  <p>${options.content}</p>
                </div>`,
      fnOnSubmit: options.fnConfirm || '',
      fnOnClose: function () {
        $('#gworks-evt-standardModal').removeClass('modal-confirmation');
        $('#gworks-evt-standardModal .modal-footer .btn-danger').addClass('btn-dark').removeClass('btn-danger');

      }
    });

    $('#gworks-evt-standardModal').addClass('modal-confirmation');
    $('#gworks-evt-standardModal .modal-footer .btn-dark').addClass('btn-danger').removeClass('btn-dark');
  }

  standardModal(isNew) {
    if (this.stdModal === null || isNew !== '') {
      this.stdModal = new StandardModal();
    }
    return this.stdModal;
  }
};

class StandardModal {
  open(options) {
    options.title = options.title || 'Standard';
    options.btnCancelShow = 'btnCancelShow' in options ? options.btnCancelShow : true;
    options.btnCancelLabel = options.btnCancelLabel || 'Cancel';
    options.btnSubmitLabel = options.btnSubmitLabel || 'Ok';
    options.content = options.content || null;
    options.contentSelector = options.contentSelector || null;
    options.clicktoclose = options.clicktoclose || false;
    options.selector = options.selector || '#gworks-evt-standardModal';
    const stdModal = $(options.selector);
    stdModal.find('.gworks-evt-standardModalLabel').html(options.title);

    const stdModalCancel = stdModal.find('.gworks-evt-standardModalCancel');
    stdModalCancel.html(options.btnCancelLabel);
    if (options.btnCancelShow) {
      stdModalCancel.show();
    } else {
      stdModalCancel.hide();
    }

    if ('small' in options) {
      $('#gworks-evt-standardModal .modal-dialog').addClass('modal-sm').removeClass('modal-lg modal-xl');
    }

    if (options.content != null) {
      stdModal.find('.gworks-evt-standardModalBody').html(options.content);
    } else if (options.contentSelector != null) {
      stdModal.find('.gworks-evt-standardModalBody').html($(options.contentSelector).html());
    }

    stdModal.on('hidden.bs.modal', function (e) {
      stdModal.find('.gworks-evt-standardModalBody').empty();
      if (options.fnOnClose) {
        options.fnOnClose();
      }
    });

    const stdModalSubmit = stdModal.find('.gworks-evt-standardModalSubmit');
    if (options.fnOnSubmit) {
      stdModalSubmit.html(options.btnSubmitLabel).show().off().on('click', function () {
        options.fnOnSubmit(stdModal.find('.gworks-evt-standardModalBody'));
      });
    } else {
      stdModalSubmit.off().hide();
    }

    if (!options.clicktoclose) {
      $(options.selector).attr('data-keyboard', 'false');
      $(options.selector).attr('data-backdrop', 'static');
    }

    if (options.fnOnLoad) {
      options.fnOnLoad(stdModal.find('.gworks-evt-standardModalBody'));
    }

    stdModal.modal('show');
    return this;
  }

  close(options) {
    let selector = '#gworks-evt-standardModal';
    if (options) {
      selector = options.selector || '#gworks-evt-standardModal';
    }
    const stdModal = $(selector);
    stdModal.modal('hide');
    setTimeout(function () {
      stdModal.removeClass('gworks-evt-MediaLibrary mediaModal modal-confirmation');
      stdModal.find('.gworks-evt-standardModalBody').empty();
    }, 300);
  }
}

},{"./gworks.core.page":27}],27:[function(require,module,exports){
module.exports = class GWorksCorePage extends require('./gworks.core.data') {
  constructor () {
    super();
    this.pageLoadFn = [];
  }

  queueForPageLoad (fn) {
    this.pageLoadFn.push(fn);
  }

  onPageLoad () {
    window.$gworks.api.setFnFailedRefresh(this.onAuthTokenExpire);

    toastr.options = {
      closeButton: true,
      debug: false,
      newestOnTop: true,
      progressBar: true,
      positionClass: 'toast-top-center',
      preventDuplicates: true,
      onclick: null,
      showDuration: 300,
      hideDuration: 100,
      timeOut: 2500,
      extendedTimeOut: 1000,
      showEasing: 'swing',
      hideEasing: 'linear',
      showMethod: 'fadeIn',
      hideMethod: 'fadeOut'
    };

    $('[data-toggle="popover"]').popover();

    $(document).on('click', '.gworks-evt-dropdown-noclick', function (e) {
      e.stopPropagation();
    });


        if (!window.configData.master) {

      const ux = window.$gworks.lookup.getUX();
      if (ux.logo) {
        $('.gworks-evt-citylogo img').attr('src', `${window.configData.filesUrl}/city/${this.getCityCode()}/logo.jpg`);
        $('.gworks-evt-citylogo').removeClass('roundLogo squareLogo rectangleLogo').addClass(ux.logoStyle);
        $('.gworks-evt-citylogo').show();
      }    

      $('.gworks-evt-data-city-displayname').html(window.$gworks.core.getCityDisplayName());
      $('.gworks-login-header').attr('src', `${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/header.jpg`);

    }

    require('./pdf.download').onPageLoad();

    if (this.isUserLoggedIn()) {
      $('.gworks-evt-searchFormBtn').on('click', function (e) {
        e.stopPropagation();
        $('.gworks-evt-searchForm').removeClass('d-none');
        $('.gworks-evt-searchBar').focus();
      });

      $(document).on('click', function (e) {
        $('.gworks-evt-searchForm').addClass('d-none');
        $('.gworks-evt-searchForm').find('.search-results-dropdown').addClass('d-none');
      });
      $('.gworks-evt-searchForm').on('click', function (e) {
        e.stopPropagation();
      });

      $('.gworks-evt-logout').on('click', function () {
        sessionStorage.removeItem('closePopUp');
        window.$gworks.core.doLogout();
        window.location = window.configData.master ? '/master/index.html' : '/index.html';
      });

      const backUrl = window.$gworks.api.getUriParam('back', null);
      if (backUrl !== null) {
        $('a.gworks-backref').attr('href', backUrl);
      }

      const passwordInput = $('.gworks-evt-passwordInput');
      $(passwordInput).wrap('<div class="passwordInput"></div>');
      $('.passwordInput').append('<button class="gworks-evt-togglePassword btn" type="button"><i class="fa fa-eye"></i></button>');

      $(document).on('click', '.gworks-evt-togglePassword', function (e) {
        $(this).toggleClass('show');
        if (passwordInput.attr('type') === 'password') {
          passwordInput.attr('type', 'text');
          $(this).html('<i class="fa fa-eye-slash"></i>');
        } else {
          passwordInput.attr('type', 'password');
          $(this).html('<i class="fa fa-eye"></i>');
        }
      });

      $('.gworks-evt-link-help').click(function () {
        if ($('.gworks-evt-help').length > 0 && $('.gworks-evt-help').html() !== '') {
          $('#gworks-evt-help').find('.modal-body').html($('.gworks-evt-help').html());
          $('#gworks-evt-help').modal('show');
        } else {
          window.$gworks.core.onWarning('Sorry, help is not available for this area');
        }
      });

      $('.gworks-evt-data-displayname').html(window.$gworks.core.getUserDisplayName());
      $('.gworks-evt-data-profilePicLetter').html(window.$gworks.core.getUserDisplayName().slice(0, 1));
    }

    $('.form-control').attr('autocomplete', 'off');
    $(document).on('click', '.gWorks-evt-copyInput', function () {
      copyClipboard($(this).closest('.input-group').find('input').val());
    });

    $(document).on('click', '.gworks-evt-clipboard', function () {
      copyClipboard($(this).attr('clipboard-text'));
    });

    for (const fn of this.pageLoadFn) {
      try {
        fn();
      } catch (e) {
        if ('redirect' in e) {
          window.location = e.redirect;
        } else {
          console.error(e);
        }
      }
    }

    delete this.pageLoadFn;
    window.$gworks.plugin.onPageLoad();
  }
};


function copyClipboard (data) {
  const textArea = document.createElement('textarea');
  textArea.value = data;
  document.body.appendChild(textArea);
  textArea.select();
  document.execCommand('Copy');
  toastr.success('Copied the text: ' + textArea.value);
  textArea.remove();
}

},{"./gworks.core.data":24,"./pdf.download":33}],28:[function(require,module,exports){
module.exports = {
  onPageLoad: async function () {

    enableDisable('plugin-payments', window.$gworks.core.isPluginPaymentsEnabled());
    enableDisable('plugin-forms', window.$gworks.core.isPluginFormsEnabled());
    enableDisable('plugin-messaging', window.$gworks.core.isPluginMessagingEnabled());
    enableDisable('plugin-cms', window.$gworks.core.isPluginCMSEnabled());
    enableDisable('plugin-utilities', window.$gworks.core.isPluginUtilitiesEnabled());
    enableDisable('plugin-311', window.$gworks.core.isPlugin311Enabled());
    enableDisable('plugin-reports', window.$gworks.core.isPluginReportsEnabled());
    enableDisable('plugin-timetracker', window.$gworks.core.isPluginTimeTracker());
    enableDisable('plugin-payroll', window.$gworks.core.isPluginPayroll());
    enableDisable('public-notices', window.$gworks.core.isPublicNoticesEnabled());
    enableDisable('agendas-minutes', window.$gworks.core.isAgendasMinutesEnabled());
    enableDisable('public-information', window.$gworks.core.isPublicNoticesEnabled() || window.$gworks.core.isAgendasMinutesEnabled())
    enableDisable('guest-payments', window.$gworks.core.isGuestPaymentsEnabled());
    enableDisable('plugin-permits', window.$gworks.core.isPluginPermitsEnabled());

    if (window.$gworks.core.isSupportUser()) {
      enableDisable('support', false);
    }

    menuOnOffPerUser();
    doMenu();
    doMenucollapse();
    checkUpgradePage();
  },

  preLoadPageCheck: function (license) {
    if (license === 'frontdesk' && !window.$gworks.core.isFrontDeskEnabled()) {
      window.location = '/s/index.html';
    } else if (license === 'plugin-payments' && !window.$gworks.core.isPluginPaymentsEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'plugin-utilities' && !window.$gworks.core.isPluginUtilitiesEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'plugin-311' && !window.$gworks.core.isPlugin311Enabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'plugin-cms' && !window.$gworks.core.isPluginCMSEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'plugin-messaging' && !window.$gworks.core.isPluginMessagingEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'plugin-forms' && !window.$gworks.core.isPluginFormsEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'public-notices' && !window.$gworks.core.isPublicNoticesEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'agendas-minutes' && !window.$gworks.core.isAgendasMinutesEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'plugin-reports' && !window.$gworks.core.isPluginReportsEnabled()) {
      window.location = '/s/fd/dashboard.html';
    } else if (license === 'guest-payments' && !window.$gworks.core.isGuestPaymentsEnabled()) {
      window.location = '/s/fd/dashboard.html';
    }
  }
};


const FINANCE_ENTITIES = 'FinanceAccounting,FinanceAccountsReceivable,' +
  'FinanceAccountsPayable,FinanceBudgeting,FinanceReports,FinanceSettings';

const COURT_ENTITIES = 'CourtTickets,CourtCases,CourtDefendantRepository,CourtReporting,CourtSettings';

function menuOnOffPerUser () {
  if (!window.$gworks.cityuser.hasRO('SuperAdmin')) {
    hideHub('settings,maps,ops,ubcloud');

    if (window.$gworks.core.isPluginPayroll() && !window.$gworks.core.isPluginTimeTracker()) {
      hideArea('timesheet');
      hideArea('leaverequest');
    }
  }

  if (window.$gworks.core.isFinanceHubEnabled() && !window.$gworks.cityuser.hasRO(FINANCE_ENTITIES)) {
    hideHub('finance');
  }

  if (!window.$gworks.cityuser.hasRO('PluginForms') &&
      !window.$gworks.cityuser.hasRO('PluginMessagingMessage') &&
      !window.$gworks.cityuser.hasRO('PluginMessagingPages') &&
      !window.$gworks.cityuser.hasRO('PluginUtilities') &&
      !window.$gworks.cityuser.hasRO('Plugin311') &&
      !window.$gworks.cityuser.hasRO('PluginReports')) {
    hideHub('frontdesk');
    hideArea('frontdesk');
  }

  if (!window.$gworks.cityuser.hasRO('HR')) {
    hideHub('hr');
  }

  if (!window.$gworks.core.isCemeteryEnabled()) {
    hideHub('cemetery');
  }

  if (!window.$gworks.core.isCourtEnabled() || !window.$gworks.cityuser.hasRO(COURT_ENTITIES)) {
    hideHub('court');
  }

  if (!window.$gworks.cityuser.hasRO('PluginMessagingPublicNotice') &&
      !window.$gworks.cityuser.hasRO('PluginMessagingPublicMeetings') &&
      !window.$gworks.cityuser.hasRO('PluginMessagingPublicFAQ') &&
      !window.$gworks.cityuser.hasRO('PluginMessagingPages') &&
      !window.$gworks.cityuser.hasRO('PluginMessagingWebsiteSettings')) {
    hideHub('storage');
  }

  if (!window.$gworks.cityuser.hasRO('PluginMessagingMessage')) {
    hideArea('messaging');
  }

  if ('authUser' in window.$gworks) {
    window.$gworks.authUser.ts = 'ts' in window.$gworks.authUser ? window.$gworks.authUser.ts : false;
    window.$gworks.authUser.pr = 'pr' in window.$gworks.authUser ? window.$gworks.authUser.pr : false;

    if (!window.$gworks.authUser.pr) {
      hideArea('leaverequest');
    }

    if (window.$gworks.authUser.pr && !window.$gworks.authUser.ts) {
      hideArea('timesheet');
    }
  }
}

function hideHub (hub) {
  hub = hub.split(',');
  for (const h of hub) {
    $(`.sidebar [license-hub=${h.trim()}]`).hide();
  }
}

function hideArea (area) {
  area = area.split(',');
  for (const h of area) {
    $(`[license-area=${h.trim()}]`).hide();
  }
}

function enableDisable(area, enabled) {
    if (typeof area === "string") {
        area = area.split(',');
    }

    for (const a of area) {
        if (enabled) {
            enableArea(a);
        } else {
            disableArea(a);
        }
    }
}

function enableArea (area) {
  $(`[license-show=${area}]`).show();
}

function disableArea (area) {
  $(`[license-hide=${area}]`).hide();
  $(`[license-remove=${area}]`).remove();

  $(`a[license-disable=${area}]`).addClass('gworks-evt-disableItem disableItem');
}

function doMenucollapse() {
  if($.ajaxSettings.url.includes('hr/list')){  
    $("aside.sidebar div[license-hub='hr']") .addClass("background mm-active")

    $("aside.sidebar a.menu-sub-employee").closest("nav").addClass("mm-show");

    $("aside.sidebar a.menu-sub-employee").addClass("sub-menu-background");
  }


    if($.ajaxSettings.url.includes('dashboard')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")

    $("aside.sidebar a.menu-sub-dashboard").closest("nav").addClass("mm-show");

    $("aside.sidebar a.menu-sub-dashboard").addClass("sub-menu-background");
  }

    if($.ajaxSettings.url.includes('payments') && !$.ajaxSettings.url.includes('guest-payments')){
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-payments").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-payments").addClass("sub-menu-background");
  }

  if($.ajaxSettings.url.includes('crm/list')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-crm").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-crm").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/plugin/311/')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-311").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-311").addClass("sub-menu-background");
  }

  if($.ajaxSettings.url.includes('forms')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-forms").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-forms").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('utilities')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-utilities").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-utilities").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('messaging')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-messaging").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-messaging").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/plugin/cms/publicnotices') ||
     $.ajaxSettings.url.includes('/plugin/cms/am') ||
     $.ajaxSettings.url.includes('/plugin/cms/faq')
     ){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-publicinfo").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-publicinfo").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/cms/pages')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-cms").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-cms").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/plugin/reports')){  
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-reports").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-reports").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('guest-payments')){
    $("aside.sidebar div[license-hub='frontdesk']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-guest-payments").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-guest-payments").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('medialibrary')){  
    $("aside.sidebar div[license-hub='storage']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-medialibrary").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-medialibrary").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/ad/settings')){  
    $("aside.sidebar div[license-hub='settings']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-settings").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-settings").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/ad/payment-settings')){  
    $("aside.sidebar div[license-hub='settings']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-paymentsettings").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-paymentsettings").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('pdf-settings')){  
    $("aside.sidebar div[license-hub='settings']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-pdfsettings").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-pdfsettings").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('reference-types')){  
    $("aside.sidebar div[license-hub='settings']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-reftypes").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-reftypes").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('security-groups')){  
    $("aside.sidebar div[license-hub='settings']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-securitygroups").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-securitygroups").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('ad/city-activity')){  
    $("aside.sidebar div[license-hub='settings']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-activity").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-activity").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/s/hr/list')){  
    $("aside.sidebar div[license-hub='hr']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-employee").closest("nav").addClass("mm-show");
    $("aside.sidebar a.menu-sub-employee").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/cemetery/')){
    $("aside.sidebar div[license-hub='cemetery']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-cemeteryhub").addClass("sub-menu-background");
  }
  if($.ajaxSettings.url.includes('/court/')){
    $("aside.sidebar div[license-hub='court']") .addClass("background mm-active")
    $("aside.sidebar a.menu-sub-courthub").addClass("sub-menu-background");
  }
}

function doMenu() {
    const upgradeUrl = window.configData.upgradeUrl;
    const shouldUseHubSidebar =
        !!(window.$gworks.core.isPluginPayroll() ||
            window.$gworks.core.isPluginPayrollDemo() ||
            window.$gworks.core.isPluginTimeTracker() ||
            window.$gworks.core.isOpsHubEnabled() ||
            window.$gworks.core.isFinanceHubEnabled() ||
            window.$gworks.core.isMapsHubEnabled() ||
            window.$gworks.core.isUtilityBillingEnabled() ||

            window.$gworks.core.isCemeteryEnabled() ||
            window.$gworks.core.isCourtEnabled());

    addMenu(shouldUseHubSidebar);

    if (!shouldUseHubSidebar && window.$gworks.core.isFrontDeskEnabled()) {
        $("a.nav-link[license-enable='frontdesk']").removeClass("disableItem").removeClass("gworks-evt-disableItem");
    }

    $('aside.sidebar a.gworks-evt-disableItem').popover({
      title: 'Not active yet',
      content: 'You do not currently have access to this. Contact gWorks to learn more and subscribe.',
      trigger: 'manual',
      placement: 'right',
      container: 'body'
    }).on('mouseenter', function () {
      const _this = this;
      $(this).popover('show');
      $('.popover').on('mouseleave', function () {
        $(_this).popover('hide');
      });
    }).on('mouseleave', function () {
      const _this = this;
      setTimeout(function () {
        if (!$('.popover:hover').length) {
          $(_this).popover('hide');
        }
      }, 50);
    }).removeAttr('data-toggle aria-controls aria-selected');

    $('aside.sidebar .gworks-evt-disableItem').on('click', function () {
      $(this).removeClass('gworks-evt-disableItem disableItem');
      $(this).popover('dispose');
    });

    if (!window.$gworks.core.isPublicNoticesEnabled() && window.$gworks.core.isAgendasMinutesEnabled()) {
      $('#div_public_information a').attr('href', '/plugin/cms/am.html');
    }

    if (shouldUseHubSidebar) {

        if (window.$gworks.core.licenseExpiration() || !window.$gworks.core.isFrontDeskEnabled()) {
            $('aside.sidebar').find('a.menu-frondesk').addClass('disableItem');
            $('#fd-nav-menu').attr('class', 'nav-link first-level-menu');
            $('#menuFrontdesk-tab').attr('href', upgradeUrl).removeAttr('data-toggle');
            $('#fd-nav-menu-sub').remove();
        }

        const hubObjects = [
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-ubaccounts'),
                qaURL: window.configData.ubURLInQA,
                URL: window.configData.ubURL,
                disabledURL: "https://www.google.com",
                enabled: window.$gworks.core.isUtilityBillingEnabled()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-opshub'),
                qaURL: window.configData.opsHubURLInQA,
                URL: window.configData.opsHubURL,
                disabledURL: "https://www.google.com",
                enabled: window.$gworks.core.isOpsHubEnabled()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-mapshub'),
                qaURL: window.configData.mapsHubURLInQA,
                URL: window.configData.mapsHubURL,
                enabled: window.$gworks.core.isMapsHubEnabled()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-cemeteryhub'),
                qaURL: '/cemetery/',
                URL: '/cemetery/',
                enabled: window.$gworks.core.isCemeteryEnabled()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-courthub'),
                qaURL: '/court/',
                URL: '/court/',
                enabled: window.$gworks.core.isCourtEnabled()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-financehub'),
                qaURL: window.configData.financeHubURLInQA,
                URL: window.configData.financeHubURL,
                enabled: window.$gworks.core.isFinanceHubEnabled()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-employee'),
                qaURL: window.$gworks.core.isPluginPayroll()
                    ? window.configData.hrEmployeeURLInQA
                    : '/s/hr/list.html',
                URL: window.$gworks.core.isPluginPayroll()
                    ? window.configData.hrEmployeeURL
                    : '/s/hr/list.html',
                enabled: true
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-payroll'),
                qaURL: window.configData.hrEmployeeURLInQA,
                URL: window.configData.hrEmployeeURL,
                enabled: window.$gworks.core.isPluginPayroll()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-timetracker'),
                qaURL: window.configData.hrTimetrackerURLInQA,
                URL: window.configData.hrTimetrackerURL,
                enabled: window.$gworks.core.isPluginTimeTracker()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-hr-reports'),
                qaURL: window.configData.hrReportsURLInQA,
                URL: window.configData.hrReportsURL,
                enabled: window.$gworks.core.isPluginPayroll()
            },
            {
                menuItems: $('aside.sidebar').find('a.menu-sub-hr-settings'),
                qaURL: window.configData.hrSettingsURLInQA,
                URL: window.configData.hrSettingsURL,
                enabled: window.$gworks.core.isPluginPayroll()
            }
        ];

        hubObjects.forEach(hub => {
            if (typeof hub.customHandling === 'function') {
                hub.customHandling(hub);
            }

              if (!hub.enabled || window.$gworks.core.licenseExpiration()) {
                const hubKey = hub.menuItems.closest("[license-hub]").attr("license-hub");
                const disabledUrl = upgradeUrl + (!!hubKey ? `?hub=${hubKey}` : "");
                hub.menuItems.addClass("disableItem").attr("href", disabledUrl);
                return;
            }

            if (window.$gworks.core.isInQaEnabled()) {
                hub.menuItems.attr('href', hub.qaURL);
            } else {
                hub.menuItems.attr('href', hub.URL);
            }
        });

        if (window.$gworks.core.isInQaEnabled()) {
            const baseMyAccountProfileURLInQa = window.configData.myAccountProfileURLInQa;
            const hrMyAccountProfileURL = baseMyAccountProfileURLInQa;
            $('aside.sidebar').find('a.menu-sub-profile').attr('href', hrMyAccountProfileURL);
            $('.top-menu-profile a, .menu-my-account').attr('href', hrMyAccountProfileURL); 
            if (window.location.pathname.indexOf("my-account/index.html") > -1) {
            }
        } else {
            const baseMyAccountProfileURL = window.configData.myAccountProfileURL;
            const hrMyAccountProfileURL = baseMyAccountProfileURL;
            $('aside.sidebar').find('a.menu-sub-profile').attr('href', hrMyAccountProfileURL);
            $('.top-menu-profile a, .menu-my-account').attr('href', hrMyAccountProfileURL); 
            if (window.location.pathname.indexOf("my-account/index.html") > -1) {

            }
        }
        const baseMyAccountLeaveBalanceURL = window.configData.myAccountLeaveBalanceURL;
        const hrMyAccountLeaveBalanceURL = baseMyAccountLeaveBalanceURL;
        $('aside.sidebar').find('a.menu-sub-leave-balance').attr('href', hrMyAccountLeaveBalanceURL);

        const baseMyAccountLeaveRequestURL = window.configData.myAccountLeaveRequestURL;
        const hrMyAccountLeaveRequestURL = baseMyAccountLeaveRequestURL;
        $('aside.sidebar').find('a.menu-sub-menu-sub-leave-request').attr('href', hrMyAccountLeaveRequestURL);
        if (window.location.pathname.indexOf("my-account-leave-requests.html") > -1) {
            window.location.href = hrMyAccountLeaveRequestURL;
        }
        const baseMyAccountTimesheetURL = window.configData.myAccountTimesheetURL;
        const hrMyAccountTimesheetURL = baseMyAccountTimesheetURL;
        $('aside.sidebar').find('a.menu-sub-timesheet').attr('href', hrMyAccountTimesheetURL);
        if (window.location.pathname.indexOf("my-account-timesheet.html") > -1) {
            window.location.href = hrMyAccountTimesheetURL;
        }

        const baseMyAccountPaystubURL = window.configData.myAccountPaystubURL;
        const hrMyAccountPaystubURL = baseMyAccountPaystubURL;
        $('aside.sidebar').find('a.menu-sub-paystub').attr('href', hrMyAccountPaystubURL);
    }


    if (shouldUseHubSidebar && window.$gworks.core.isCityPortal()) {
        const metisMenu = require('../../../devops/node_modules/metismenujs');

        new metisMenu('#side-menu', {
            triggerElement: '.nav-link',
            parentTrigger: '.nav-item',
            subMenu: '.nav.flex-column'
        });
    }
}

function addMenu(shouldUseHubSidebar) {
    const citySidebarHubContent = $("#city-sidebar-hub").html();
    const citySidebarContent = $("#city-sidebar").html();

      $("#city-sidebar-hub").remove();
    $("#city-sidebar").remove();

    let choosenSidebar = citySidebarContent

    if(shouldUseHubSidebar) {
      choosenSidebar = citySidebarHubContent
    }

    $("#addMenuHere").replaceWith(choosenSidebar);
}

function checkUpgradePage() {
    const isUpgradePage = location.pathname.toLowerCase() === window.configData.upgradeUrl.toLowerCase();
    if (!isUpgradePage || !location.search) return;

    const hubFrameMap = new Map(Object.entries({
        "finance": "https://pages.gworks.com/finance-hub-in-product-sign-up",
        "ubcloud": "https://pages.gworks.com/ub-hub-in-product-sign-up",
        "operations": "https://pages.gworks.com/operations-hub-in-product-sign-up",
        "maps": "https://pages.gworks.com/maps-hub-in-product-sign-up",
        "frontdesk": "https://pages.gworks.com/frontdesk-in-product-sign-up"
    }));
    const matcher = new RegExp('hub=([^&]*)');
    const match = matcher.exec(location.search);
    const hubKey = match && match[1];

    if (!hubFrameMap.has(hubKey)) return;

    $(".page-container .page-content-wrapper .content").html(`<iframe src="${hubFrameMap.get(hubKey)}" scrolling="no" style="width: 100%; height: 100vh; border: none;"></iframe>`);
}

},{"../../../devops/node_modules/metismenujs":1}],29:[function(require,module,exports){
module.exports = {

  setup: function () {
    $('[liveshow-group-src]').each(function () {
      const group = $(this).attr('liveshow-group-src');
      $(`[liveshow-group=${group}]`).hide();

      $(this).on('change', function () {
        $(`[liveshow-group=${group}]`).hide();

        const el = $(this)[0];
        if (el.tagName === 'INPUT' && (el.type.toLowerCase() === 'checkbox' || el.type.toLowerCase() === 'radio')) {
          if (el.checked === true) {
            $(`[liveshow-group=${group}]`).each(function () {
              if (typeof $(this).attr('liveshow-checked') !== 'undefined') {
                if ($(this).attr('liveshow-checked') === 'true') {
                  $(this).show();
                }
              }
            });
          } else {
            $(`[liveshow-group=${group}]`).each(function () {
              if (typeof $(this).attr('liveshow-checked') !== 'undefined') {
                if ($(this).attr('liveshow-checked') === 'false') {
                  $(this).show();
                }
              }
            });
          }
        } else {
          const val = $(this).val();
          $(`[liveshow-group=${group}]`).each(function () {
            if (typeof $(this).attr('liveshow-val') !== 'undefined') {
              const possibleVals = $(this).attr('liveshow-val').split(',');
              if (possibleVals.includes(val)) {
                $(this).show();
              }
            }
          });
        }
      });
    });
  },


  trigger: function () {
    $('[liveshow-group-src]').trigger('change');
  }

}
;

},{}],30:[function(require,module,exports){
class Lookup {
  constructor () {
    this.refTypes = {};
    this.city = {};
    this.tokenV = 'gworks_v250101';
  }

  clearAll () {
    localStorage.removeItem('gworks_reftype');
    localStorage.removeItem(this.tokenV);
  }

  getRef (scope) {
    return this.refTypes[scope];
  }

  getUsStates () {
    return [{ short: '', long: 'State' }, { short: 'AL', long: 'Alabama' }, { short: 'AK', long: 'Alaska' }, { short: 'AS (US Territory)', long: 'American Samoa (US Territory)' }, { short: 'AZ', long: 'Arizona' }, { short: 'AR', long: 'Arkansas' }, { short: 'AA', long: 'Armed Forces America' }, { short: 'AE', long: 'Armed Forces Europe' }, { short: 'AP', long: 'Armed Forces Pacific' }, { short: 'CA', long: 'California' }, { short: 'CO', long: 'Colorado' }, { short: 'CT', long: 'Connecticut' }, { short: 'DE', long: 'Delaware' }, { short: 'DC', long: 'District of Columbia' }, { short: 'FL', long: 'Florida' }, { short: 'GA', long: 'Georgia' }, {short: 'GU (US Territory)', long: 'Guam (US Territory)'}, { short: 'HI', long: 'Hawaii' }, { short: 'ID', long: 'Idaho' }, { short: 'IL', long: 'Illinois' }, { short: 'IN', long: 'Indiana' }, { short: 'IA', long: 'Iowa' }, { short: 'KS', long: 'Kansas' }, { short: 'KY', long: 'Kentucky' }, { short: 'LA', long: 'Louisiana' }, { short: 'ME', long: 'Maine' }, { short: 'MD', long: 'Maryland' }, { short: 'MA', long: 'Massachusetts' }, { short: 'MI', long: 'Michigan' }, { short: 'MN', long: 'Minnesota' }, { short: 'MS', long: 'Mississippi' }, { short: 'MO', long: 'Missouri' }, { short: 'MT', long: 'Montana' }, { short: 'NE', long: 'Nebraska' }, { short: 'NV', long: 'Nevada' }, { short: 'NH', long: 'New Hampshire' }, { short: 'NJ', long: 'New Jersey' }, { short: 'NM', long: 'New Mexico' }, { short: 'NY', long: 'New York' }, { short: 'NC', long: 'North Carolina' }, { short: 'ND', long: 'North Dakota' }, { short: 'OH', long: 'Ohio' }, { short: 'OK', long: 'Oklahoma' }, { short: 'OR', long: 'Oregon' }, { short: 'PA', long: 'Pennsylvania' }, { short: 'PR (US Territory)', long: 'Puerto Rico (US Territory)' }, { short: 'RI', long: 'Rhode Island' }, { short: 'SC', long: 'South Carolina' }, { short: 'SD', long: 'South Dakota' }, { short: 'TN', long: 'Tennessee' }, { short: 'TX', long: 'Texas' }, { short: 'UT', long: 'Utah' }, { short: 'VT', long: 'Vermont' }, { short: 'VA', long: 'Virginia' }, { short: 'VI (US Territory)', long: 'Virgin Islands (US Territory)' }, { short: 'WA', long: 'Washington' }, {short: 'WV', long: 'West Virginia'},{ short: 'WI', long: 'Wisconsin' }, { short: 'WY', long: 'Wyoming' }, { short: '-', long: 'Non US State' }];
  }

  setCityCode (cityCode) {
    this.city.cityCode = cityCode;
    return this;
  }

  getCityName () {
    return this.city.cityName;
  }

  getCityFeatures () {
    return this.city.f;
  }

  getCityCode () {
    return this.city.cityCode;
  }

  getCityContact () {
    return ('contact' in this.city && this.city.contact != null) ? this.city.contact : {};
  }

  licenseExpiration() {
    return this.city.cityLicenseExpiration;
  }

  getUX () {
    return ('ux' in this.city) ? this.city.ux : { logo: false, logoStyle: 'rectangleLogo', logoSize: 'logo-lg' };
  }

  setUX (data) {
    const localData = localStorage.getItem(this.tokenV);
    if (localData) {
      const fields = JSON.parse(localData);

      fields.ux.logo = data.logo;
      fields.ux.logoStyle = data.logoStyle;
      fields.ux.logoSize = data.logoSize;
      const newData = JSON.stringify(fields);
      localStorage.setItem(this.tokenV, newData);
      const logoSrc = $('.gworks-evt-genralSettings').data('logoData');
      if (logoSrc) {
        $('.gworks-evt-citylogo img').attr('src', logoSrc);
      }
      if (fields.ux.logo) {
        $('.gworks-evt-citylogo').show();
      } else {
        $('.gworks-evt-citylogo').hide();
      }
    }
  }

  resetUX () {
    const localData = localStorage.getItem(this.tokenV);
    if (localData) {
      const fields = JSON.parse(localData);
      fields.ux.logo = false;
      fields.ux.logoStyle = 'rectangleLogo';
      fields.ux.logoSize = 'logo-lg';

      const newData = JSON.stringify(fields);
      localStorage.setItem(this.tokenV, newData);
      $('.gworks-evt-citylogo').hide();
    }
  }

  getDomain () {
    return ('domain' in this.city) && ('base' in this.city.domain) ? this.city.domain.base : null;
  }

  getDomainPage () {
    return ('domain' in this.city) && ('page' in this.city.domain) ? this.city.domain.page : null;
  }

  getDomainMedia () {
    return ('domain' in this.city) && ('media' in this.city.domain) ? this.city.domain.media : null;
  }

  getETag () {
    return 'etag' in this.city ? this.city.etag : 0;
  }

  getLabelForId (scope, id) {
    id = Number(id);
    for (const ref of this.refTypes[scope]) {
      if (ref.id === id) {
        return ref.label;
      }
    }
    return '';
  }

  getLabel (id) {
    id = Number(id);
    for (const scope in this.refTypes) {
      for (const ref of this.refTypes[scope]) {
        if (ref.id === id) {
          return ref.label;
        }
      }
    }
    return '';
  }

  setFeatureFlags (featureFlags) {
    this.city = 'city' in this ? this.city : {};
    this.city.f = featureFlags;
  }

  saveData (data) {
    this.refTypes = {};
    for (const ref of data.ref_type) {
      if (typeof this.refTypes[ref.sc] === 'undefined') {
        this.refTypes[ref.sc] = [];
      }
      this.refTypes[ref.sc].push({
        id: ref.lb.match(/absorb|passed through/) ? ref.lb : ref.id,
        label: capitalize(ref.lb),
        sys: ref.sy
      });
    }

    this.city = {
      ux: data.ux,
      domain: data.domain,
      contact: data.contact,
      cityCode: data.cityCode,
      cityName: data.cityName,
      f: data.f,
      etag: data.etag,
      saveTime: new Date().getTime()
    };

    localStorage.setItem('gworks_reftype', JSON.stringify(this.refTypes));
    localStorage.setItem(this.tokenV, JSON.stringify(this.city));
  }

  loadViaCityCode (fnSuccess) {
    this.city = localStorage.getItem(this.tokenV);
    if (this.city != null) {
      this.city = JSON.parse(this.city);
      this.refTypes = JSON.parse(localStorage.getItem('gworks_reftype'));
      if (fnSuccess) {
        fnSuccess();
      }
      return;
    }

    const this_ = this;
    window.$gworks.api.get({
      uri: '/core/public/utils/lookup/common/' + window.$gworks.core.getCityCode(),
      fnSuccess: function (data) {
        this_.saveData(data);
        if (fnSuccess) {
          fnSuccess();
        }
      },
      fnError: function (data) {
        console.error(data);
      }
    });
  }

  loadViaDomain (fnSuccess, fnNotFound) {
    this.city = localStorage.getItem(this.tokenV);

    if (this.city != null) {
      this.city = JSON.parse(this.city);

      const FIFTEENMINS = 1000 * 60 * 15;
      if (this.city.saveTime + FIFTEENMINS > new Date().getTime()) {
        this.refTypes = JSON.parse(localStorage.getItem('gworks_reftype'));
        if (fnSuccess) {
          fnSuccess();
        }
        return;
      }
    }

    const this_ = this;
    window.$gworks.api.get({
      uri: `/core/public/utils/lookup/domain/${window.location.hostname}`,
      fnSuccess: function (data) {
        this_.saveData(data);
        if (fnSuccess) {
          fnSuccess();
        }
      },
      fnError: function (data) {
        console.error(data);
        if (fnNotFound) {
          fnNotFound();
        }
      }
    });
  }
}

function capitalize (d) {
  const words = d.split(' ');
  for (let x = 0; x < words.length; x++) {
    words[x] = words[x].charAt(0).toUpperCase() + words[x].slice(1);
  }
  return words.join(' ');
}

module.exports = new Lookup();

},{}],31:[function(require,module,exports){
module.exports = {

  accessToken: 'pk.eyJ1Ijoia3VtYXJnYXVyYXYyNTI1IiwiYSI6ImNrZHN5a3pzcjBtbzIyc21wNzltMTk3OXQifQ.omjaE2Iffmb6zkWHPcD5lA',

  generateMapByAddress: function (selector, address) {
    if ('cityLookupCache' in this === false) {
      this.cityLookupCache = {};
    }

    if (address['address.city'] in this.cityLookupCache) {
      const response = this.cityLookupCache[address['address.city']];
      this.generateMap(selector, response[0].lat, response[0].lon);
    } else {
      const thisInst = this;
      $.get(`https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${address['address.city']}`)
        .done(function (response) {
          if (response) {
            thisInst.cityLookupCache[address['address.city']] = response;

            if (response.length > 0) {
              thisInst.generateMap(selector, response[0].lat, response[0].lon);
            } else {
              $.get('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=Omaha, Nebraska')
                .done(function (response) {
                  thisInst.generateMap(selector, response[0].lat, response[0].lon);
                });
            }
          }
        })
        .fail(function (error) {
          window.$gworks.core.onError(error);
        });
    }
  },

  generateMap: function (selector, lat, long, popText = null) {
    $(selector).find('#gworks-data-location-map').html(`<div id="leafletMapView">${window.$gworks.core.getLoadingHtml()}</div>`);

    const latitude = (lat) || 0;
    const longitude = (long) || 0;

    $(selector).find('#gworks-data-location-map').attr('gworks-data-lat', latitude);
    $(selector).find('#gworks-data-location-map').attr('gworks-data-long', longitude);

    const mapLocation = new L.map('leafletMapView');

    const mapLayer = new L.tileLayer(`https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token=${this.accessToken}`, {
      maxZoom: 18,
      id: 'mapbox/streets-v11',
      tileSize: 512,
      zoomOffset: -1,
      accessToken: this.accessToken
    });
    mapLocation.setView([latitude, longitude], 13);
    mapLocation.addLayer(mapLayer);

    const marker = new L.marker([latitude, longitude]).addTo(mapLocation);
    marker.on('dragend', function (e) {
      console.log(marker.getLatLng().latitude, marker.getLatLng().lng);
      $(selector).find('#gworks-data-location-map').attr('gworks-data-lat', latitude);
      $(selector).find('#gworks-data-location-map').attr('gworks-data-long', longitude);
    });
    mapLocation.on('click', function (e) {
      marker.setLatLng(e.latlng);
      $(selector).find('#gworks-data-location-map').attr('gworks-data-lat', latitude);
      $(selector).find('#gworks-data-location-map').attr('gworks-data-long', longitude);
    });

    if (popText) {
      marker.bindPopup(`<b>${popText}</b>`).openPopup();
    }

    mapLocation.on('click', function (e) {
      $(selector).find('#gworks-data-location-map').attr('gworks-data-lat', e.latlng.lat);
      $(selector).find('#gworks-data-location-map').attr('gworks-data-long', e.latlng.lng);
    });
  }
}
;

},{}],32:[function(require,module,exports){
(function (global){(function (){
module.exports = class Oauth {
  constructor (api) {
    this.api = api;
    this.activeAccessToken = null;
    this.fnFailedRefresh = null;
    this.siteMode = window.configData.siteMode || 'citizen';
    this.storageKey = `${this.siteMode}__gworks__jwt`;
  }

  clear () {
    localStorage.removeItem(this.storageKey);
    localStorage.removeItem(this.storageKey + '_email');
  }

  doLogout () {
    this.clear();
    window.$gworks.lookup.clearAll();
    this.activeAccessToken = null;
  }

  setFnFailedRefresh (fn) {
    this.fnFailedRefresh = fn;
  }

  getEmail () {
    let email = localStorage.getItem(this.storageKey + '_email');

    if (email === null && this.storageKey === 'city__gworks__jwt') {
      email = localStorage.getItem('master__gworks__jwt_email');
    }

    return email == null ? null : email.toLowerCase();
  }

  getRefreshToken() {
    const refreshToken = JSON.parse(localStorage.getItem(this.storageKey));
    return refreshToken == null ? null : refreshToken.refresh;
  }

  doLogin (username, password, citycode, fnGood, fnBad) {
    this.clear();
    window.$gworks.lookup.clearAll();

    const data = {
      password: password,
      email: username
    };
    if (citycode != null && citycode !== '') {
      data.citycode = citycode;
    }

    const thisInst = this;
    thisInst.api.post({
      uri: `/core/public/oauth/${thisInst.siteMode}/login`,
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          localStorage.setItem(thisInst.storageKey + '_email', username.toLowerCase());
          thisInst._storeTokens(data);
          thisInst.setRefreshCallback(true);
          if (fnGood) {
            fnGood();
          }
          return;
        }

        if (fnBad) {
          fnBad(data);
        }
      },
      fnError: function (data) {
        thisInst._unauthorizedUser();
        if (fnBad) {
          fnBad(data);
        }
      },
      data: data
    });
  }

  doLoginCitizenSupport (token, fnGood, fnBad) {
    this.clear();
    window.$gworks.lookup.clearAll();

    const thisInst = this;
    thisInst.api.post({
      uri: '/core/public/oauth/citizen/support/login/',
      data: {
        token: token
      },
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          thisInst._storeTokens(data);
          thisInst.setRefreshCallback(true);
          if (fnGood) {
            fnGood();
          }
          return;
        }

        if (fnBad) {
          fnBad(data);
        }
      },
      fnError: function (data) {
        thisInst._unauthorizedUser();
        if (fnBad) {
          fnBad(data);
        }
      }
    });
  }

  doLoginGuestPayments(cityId, cityName, fnGood, fnBad) {
    this.clear();
    const thisInst = this;
    thisInst.api.post({
      uri: '/payments/public/vendor/guest-payments/generate-session-token',
      data: {
        cityId: cityId,
        cityName: cityName
      },
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          thisInst._storeTokens(data);
          thisInst.setRefreshCallback(false);
          if (fnGood) {
            fnGood(data);
          }
          return;
        }
        if (fnBad) {
          fnBad(data);
        }
      },
      fnError: function (data) {
        thisInst._unauthorizedUser();
        if (fnBad) {
          fnBad(data);
        }
      }
    });
  }

  doLoginAutoTest (cityCode, email, fnGood, fnBad) {
    this.clear();
    window.$gworks.lookup.clearAll();

    const thisInst = this;
    thisInst.api.get({
      uri: `/core/testauto/login/citizen/${cityCode}/${email}`,
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          localStorage.setItem(thisInst.storageKey + '_email', email.toLowerCase());
          thisInst._storeTokens(data);
          thisInst.setRefreshCallback(true);
          if (fnGood) {
            fnGood();
          }
          return;
        }

        if (fnBad) {
          fnBad(data);
        }
      },
      fnError: function (data) {
        thisInst._unauthorizedUser();
        if (fnBad) {
          fnBad(data);
        }
      }
    });
  }

  doLoginSupport (token, fnGood, fnBad) {
    window.$gworks.lookup.clearAll();

    const thisInst = this;
    thisInst.api.post({
      uri: `/core/public/oauth/${thisInst.siteMode}/login-support`,
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          thisInst._storeTokens(data);
          thisInst.setRefreshCallback(true);
          if (fnGood) {
            fnGood();
          }
          return;
        }

        if (fnBad) {
          fnBad(data);
        }
      },
      fnError: function (data) {
        thisInst._unauthorizedUser();
        if (fnBad) {
          fnBad(data);
        }
      },
      data: {
        token: token
      }
    });
  }

  doLoginAutotest (cityCode, email, fnGood, fnBad) {
    window.$gworks.lookup.clearAll();

    const thisInst = this;
    thisInst.api.get({
      uri: `/core/testauto/login/city/${cityCode}/${email}`,
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          thisInst._storeTokens(data);
          thisInst.setRefreshCallback(true);
          if (fnGood) {
            fnGood();
          }
          return;
        }

        if (fnBad) {
          fnBad(data);
        }
      },
      fnError: function (data) {
        thisInst._unauthorizedUser();
        if (fnBad) {
          fnBad(data);
        }
      }
    });
  }


  initSecure () {
    let tokens = localStorage.getItem(this.storageKey);
    tokens = (tokens != null) ? JSON.parse(tokens) : null;
    if (tokens == null) {
      localStorage.setItem(`${this.siteMode}_redirectUrl`, window.location.href);
      return false;
    }

    if (this.siteMode === 'citizen' || this.siteMode === 'city' || this.siteMode === 'master') {
      this.activeAccessToken = tokens.access;
    } else {
      this.activeAccessToken = tokens.access[tokens.activeAccessTokenIdx];
    }

       const payload = jwt_decode(this.activeAccessToken);
    const browserTime = Math.ceil(new Date().getTime() / 1000);

    if ('ff' in payload) {
      window.$gworks.lookup.setFeatureFlags(payload.ff);
    }

    if (browserTime > payload.exp) {
      localStorage.setItem(`${this.siteMode}_redirectUrl`, window.location.href);
      return false;
    } else {
      return this.setRefreshCallback();
    }
  }

  getToken(){
    let tokens = localStorage.getItem(this.storageKey);
    tokens = (tokens != null) ? JSON.parse(tokens) : null;
    if (tokens == null) {
      localStorage.setItem(`${this.siteMode}_redirectUrl`, window.location.href);
      return false;
    }
    if (this.siteMode === 'citizen' || this.siteMode === 'city' || this.siteMode === 'master') {
      this.activeAccessToken = tokens.access;
    } else {
      this.activeAccessToken = tokens.access[tokens.activeAccessTokenIdx];
    }
    return this.activeAccessToken;
  }


  getActiveAccessToken () {
    return this.activeAccessToken;
  }


  _storeTokens (data) {
    data.activeAccessTokenIdx = 0;
    data.browserTime = Math.ceil(new Date().getTime() / 1000);
    localStorage.setItem(this.storageKey, JSON.stringify(data));
  }

  _unauthorizedUser () {
    localStorage.removeItem(this.storageKey);
  }


  setRefreshCallback (_settimeout = true) {
    let tokens = localStorage.getItem(this.storageKey);
    tokens = (tokens != null) ? JSON.parse(tokens) : null;

    if (tokens == null) {
      localStorage.removeItem(this.storageKey);
      if (this.fnFailedRefresh != null) {
        this.fnFailedRefresh();
      }
      return false;
    }

    if (this.siteMode === 'citizen' || this.siteMode === 'city' || this.siteMode === 'master') {
      this.activeAccessToken = tokens.access;
    } else {
      this.activeAccessToken = tokens.access[tokens.activeAccessTokenIdx];
    }

    window.$gworks = window.$gworks || {};
    window.$gworks.authUser = jwt_decode(this.activeAccessToken);

    window.$gworks.authUser.sv = 'sv' in window.$gworks.authUser ? window.$gworks.authUser.sv : 1;
    window.$gworks.authUser.fam = 'fam' in window.$gworks.authUser ? window.$gworks.authUser.fam : false;
    window.$gworks.authUser.support = 'support' in window.$gworks.authUser ? window.$gworks.authUser.support : false;

    const browserTime = Math.ceil(new Date().getTime() / 1000);
    const timeOut = 1000 * (window.$gworks.authUser.exp - browserTime - 300);

    if (_settimeout && timeOut > 0) {
      const thisInst = this;
      setTimeout(function () {
        thisInst.refreshToken();
      }, timeOut);
    }
    return true;
  }


  refreshToken (_settimeout = true) {
    let tokens = localStorage.getItem(this.storageKey);
    tokens = (tokens !== null) ? JSON.parse(tokens) : null;
    if (tokens == null) {
      if (this.fnFailedRefresh != null) {
        this.fnFailedRefresh();
      }
      return;
    }

    const thisInst = this;
    const activeAccessTokenIdx = tokens.activeAccessTokenIdx;

    thisInst.api.post({
      uri: `/core/public/oauth/${this.siteMode}/refresh`,
      data: {
        refresh: tokens.refresh,
        lookupEtag: window.$gworks.lookup.getETag()
      },
      fnSuccess: function (data) {
        if (data.refresh && data.access) {
          data.browserTime = Math.ceil(new Date().getTime() / 1000);
          data.activeAccessTokenIdx = activeAccessTokenIdx;
          if (data.activeAccessTokenIdx > data.access.length) {
            data.activeAccessTokenIdx = 0;
          }

          if ('lookup' in data) {
            window.$gworks.lookup.saveData(data.lookup);
          }

          localStorage.setItem(thisInst.storageKey, JSON.stringify(data));
          thisInst.setRefreshCallback(true);
        }
      },

      fnError: function (data) {
        localStorage.removeItem(this.storageKey);
        thisInst.activeAccessToken = null;

        if (thisInst.fnFailedRefresh != null) {
          thisInst.fnFailedRefresh();
        }
      }
    });
  }
};

!(function a (b, c, d) {
  function e (g, h) {
    if (!c[g]) {
      if (!b[g]) {
        const i = typeof require === 'function' && require;
        if (!h && i) return i(g, !0);
        if (f) return f(g, !0);
        const j = new Error("Cannot find module '" + g + "'");
        throw j.code = 'MODULE_NOT_FOUND', j;
      }
      const k = c[g] = {
        exports: {}
      };
      b[g][0].call(k.exports, function (a) {
        const c = b[g][1][a];
        return e(c || a);
      }, k, k.exports, a, b, c, d);
    }
    return c[g].exports;
  }
  for (var f = typeof require === 'function' && require, g = 0; g < d.length; g++) e(d[g]);
  return e;
}({
  1: [function (a, b, c) {
    function d (a) {
      this.message = a;
    }

    function e (a) {
      const b = String(a).replace(/=+$/, '');
      if (b.length % 4 == 1) throw new d("'atob' failed: The string to be decoded is not correctly encoded.");
      for (var c, e, g = 0, h = 0, i = ''; e = b.charAt(h++); ~e && (c = g % 4 ? 64 * c + e : e, g++ % 4) ? i += String.fromCharCode(255 & c >> (-2 * g & 6)) : 0) e = f.indexOf(e);
      return i;
    }
    var f = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=';
    d.prototype = new Error(), d.prototype.name = 'InvalidCharacterError', b.exports = typeof window !== 'undefined' && window.atob && window.atob.bind(window) || e;
  }, {}],
  2: [function (a, b, c) {
    function d (a) {
      return decodeURIComponent(e(a).replace(/(.)/g, function (a, b) {
        let c = b.charCodeAt(0).toString(16).toUpperCase();
        return c.length < 2 && (c = '0' + c), '%' + c;
      }));
    }
    var e = a('./atob');
    b.exports = function (a) {
      let b = a.replace(/-/g, '+').replace(/_/g, '/');
      switch (b.length % 4) {
        case 0:
          break;
        case 2:
          b += '==';
          break;
        case 3:
          b += '=';
          break;
        default:
          throw 'Illegal base64url string!';
      }
      try {
        return d(b);
      } catch (c) {
        return e(b);
      }
    };
  }, {
    './atob': 1
  }],
  3: [function (a, b, c) {
    'use strict';

    function d (a) {
      this.message = a;
    }
    const e = a('./base64_url_decode');
    d.prototype = new Error(), d.prototype.name = 'InvalidTokenError', b.exports = function (a, b) {
      if (typeof a !== 'string') throw new d('Invalid token specified');
      b = b || {};
      const c = b.header === !0 ? 0 : 1;
      try {
        return JSON.parse(e(a.split('.')[c]));
      } catch (f) {
        throw new d('Invalid token specified: ' + f.message);
      }
    }, b.exports.InvalidTokenError = d;
  }, {
    './base64_url_decode': 2
  }],
  4: [function (a, b, c) {
    (function (b) {
      const c = a('./lib/index');
      typeof b.window.define === 'function' && b.window.define.amd ? b.window.define('jwt_decode', function () {
        return c;
      }) : b.window && (b.window.jwt_decode = c);
    }).call(this, typeof global !== 'undefined' ? global : typeof self !== 'undefined' ? self : typeof window !== 'undefined' ? window : {});
  }, {
    './lib/index': 3
  }]
}, {}, [4]));

}).call(this)}).call(this,typeof global !== "undefined" ? global : typeof self !== "undefined" ? self : typeof window !== "undefined" ? window : {})
},{}],33:[function(require,module,exports){
module.exports.onPageLoad = function () {
  $(document).on('click', '.gworks-evt-pdf-download', function (e) {
    if (typeof $(this).attr('pdf') !== 'undefined') {
      e.stopPropagation();
      return;
    } else if (typeof $(this).data('status') !== 'undefined') {
      e.stopPropagation();
      e.preventDefault();
      return;
    }

    e.stopPropagation();
    e.preventDefault();
    $(this).data('label', $(this).html());
    $(this).html('<i>preparing PDF</i>');
    $(this).data('status', 'preparing');

    pdfFetch($(this));
  });
};


function pdfFetch (el) {
  const secureCall = typeof el.attr('gworks-secure-uri') !== 'undefined';
  const uri = typeof el.attr('gworks-uri') !== 'undefined' ? el.attr('gworks-uri') : `/core/public/utils/pdf/${window.$gworks.core.getCityCode()}/${el.attr('gworks-typeid')}/${el.attr('gworks-id')}`;

  if (typeof el.data('retry') === 'undefined') {
    el.data('retry', 1);
  }

  if (el.data('retry') > 20) {
    el.html('unavailable; try again later');
    return;
  }

  const options = {
    uri: (typeof el.attr('gworks-secure-uri') !== 'undefined') ? el.attr('gworks-secure-uri') : uri,
    fnSuccess: function (data) {
      if (data.status === 'wait') {
        setTimeout(function () {
          el.data('retry', el.data('retry') + 1);
          pdfFetch(el);
        }, 5000);
      } else if (data.status === 'ready') {
        el.html(el.data('label'));
        el.data('status', 'ready');
        el.attr('pdf', true).attr('href', data.signedUrl);
        el[0].click();
      }
    },
    fnError: function (data) {
      el.html(el.data('label'));
      window.$gworks.core.onWarning(data);
    }
  };

  if (secureCall) {
    window.$gworks.api.getSecure(options);
  } else {
    window.$gworks.api.get(options);
  }
}

},{}],34:[function(require,module,exports){
class PlugInBase {
  constructor (name) {
    this.name = name;
  }

  getName () {
    return this.name;
  }

  onPageLoad () {}
}

window.$PlugInBaseClass = PlugInBase;


module.exports = {

  is: function (name) {
    return `plugin${name}` in this.plugins;
  },

  get: function (name) {
    return this.plugins[`plugin${name}`];
  },

  register: function (obj) {
    this.plugins = this.plugins || {};
    this.plugins[obj.getName()] = obj;
  },

  renderSnippet (options) {
    options.plugin = options.plugin || null;
    options.uri = options.uri || null;
    options.content = options.content || null;
    options.fnSuccess = options.fnSuccess || null;

    if (options.plugin === null || !this.is(options.plugin)) {
      return;
    }

    if (options.content != null) {
      $(options.content).html(window.$gworks.core.getLoadingHtml());
      $(options.content).load(`/plugin/${options.plugin}/${options.uri}`, function (responseText, textStatus, jqXHR) {
        if (jqXHR.status === 200 && options.fnSuccess != null) {
          setTimeout(function () {
            options.fnSuccess();
          }, 1);
        }
      });
    } else if (options.fnSuccess != null) {
      setTimeout(function () {
        options.fnSuccess();
      }, 1);
    }
  },

  loadPage: function (selector) {
    const plugin = window.$gworks.api.getUriParam('plugin', null);
    if (plugin == null || !window.$gworks.plugin.is(plugin)) {
      window.location = '/s/index.html';
    }

    window.$gworks.plugin.renderSnippet({
      plugin: plugin,
      uri: window.$gworks.api.getUriParam('uri', 'index.html'),
      content: selector
    });
  },

  onPageLoad: function () {
    for (const pluginName in this.plugins) {
      try {
        this.plugins[pluginName].onPageLoad();
      } catch (e) {
        console.error(pluginName + ':' + e);
      }
    }
  }

};

},{}]},{},[25]);
