(function(){function r(e,n,t){function o(i,f){if(!n[i]){if(!e[i]){var c="function"==typeof require&&require;if(!f&&c)return c(i,!0);if(u)return u(i,!0);var a=new Error("Cannot find module '"+i+"'");throw a.code="MODULE_NOT_FOUND",a}var p=n[i]={exports:{}};e[i][0].call(p.exports,function(r){var n=e[i][1][r];return o(n||r)},p,p.exports,r,e,n,t)}return n[i].exports}for(var u="function"==typeof require&&require,i=0;i<t.length;i++)o(t[i]);return o}return r})()({1:[function(require,module,exports){
module.exports = {

  set: function (data) {
    if (data['cms_meeting.meeting_ts'] != null && data['cms_meeting.meeting_ts'] !== '') {
      data['cms_meeting.meeting_ts'] = moment(data['cms_meeting.meeting_ts'], moment.defaultFormat).format();

      data['cms_meeting.date'] = data['cms_meeting.meeting_ts'].split('T')[0];
      data['cms_meeting.time'] = data['cms_meeting.meeting_ts'].split('T')[1];
      data['cms_meeting.time'] = data['cms_meeting.time'].substring(0, data['cms_meeting.time'].indexOf(':', 3));
    }
    window.$gworks.form.setData('#gworks-evt-am-form', data);

    for (const section of data['cms_meeting.data']) {
      require('./section').render(section);
    }

    require('./files').render(data['cms_meeting.files']);

    if ('cms_meeting.mod_ts' in data) {
      $('.gworks-evt-updatedts').html(window.$gworks.core.renderDateLongTime(data['cms_meeting.mod_ts']));
      $('.gworks-evt-updated').show();
    }

    require('./ui').setup(data);
  },


  save: function (formData) {
    formData = (typeof formData === 'undefined') ? require('./data').fetch() : formData;
    if (formData != null) {
      const messId = $('#gworks-evt-am-form').data('messId');

      const apiData = {
        uri: (messId == null) ? '/cms/secure/city/meeting/' : `/cms/secure/city/meeting/${messId}`,
        data: formData,
        fnSuccess: function (data) {
          window.$gworks.core.updateSubTitle(formData['cms_meeting.title']);
          $('#gworks-evt-am-form').data('messId', data['cms_meeting.id']);
          $('.gworks-evt-updatedts').html(window.$gworks.core.renderDateLongTime(data['cms_meeting.mod_ts']));
          $('.gworks-evt-updated').show();

          window.$gworks.core.reWriteUrl(`cms_meeting.id=${data['cms_meeting.id']}`);

          $('.gworks-page-clone, .gworks-page-delete').show();
          $('.gworks-evt-pdf-download').removeAttr('pdf').removeData('status').removeData('retry', 1).attr('href', '#');
          require('./ui').setup(data);

          window.$gworks.form.enableButtons();
          window.$gworks.core.onSuccess('successfully updated');
          setupStickyBar();
        },
        fnError: function (data) {
          window.$gworks.form.enableButtons();
          window.$gworks.core.onWarning(data);
        }
      };

      window.$gworks.form.disableButtons();
      if (messId == null) {
        window.$gworks.api.postSecure(apiData);
      } else {
        window.$gworks.api.putSecure(apiData);
      }
    }
  },


  fetch: function () {
    window.$gworks.form.clear('#gworks-evt-am-form');
    if (!window.$gworks.form.validate('#gworks-evt-am-form')) {
      window.$gworks.core.onWarning('Please fill all the required fields');
      return null;
    }
    const formData = window.$gworks.form.getData('#gworks-evt-am-form', 'ALL');
    formData['cms_meeting.meeting_ts'] = formData['cms_meeting.date'] + 'T' + formData['cms_meeting.time'] + ':00';
    formData['cms_meeting.meeting_ts'] = moment(formData['cms_meeting.meeting_ts']).utc().format();

    formData['cms_meeting.data'] = [];
    $('#gworks-evt-am-form .gworks-section').each(function () {
      const section = require('./section').getData($(this));
      formData['cms_meeting.data'].push(section);
    });

    formData['cms_meeting.section_count'] = formData['cms_meeting.data'].length;
    formData['cms_meeting.data'] = JSON.stringify(formData['cms_meeting.data']);

    const files = require('../../js/medialibrary.popup').fetchFiles();
    formData['cms_meeting.files'] = JSON.stringify(files);

    if (formData['cms_meeting.section_count'] === 0) {
      window.$gworks.core.onWarning('Please specify at least one section');
      return null;
    } else {
      return formData;
    }
  },
  setupStickyBar: setupStickyBar

};


function setupStickyBar () {
  $('body').addClass('isPageHeaderSticked isRightSidebarSticked');
  const sidebar = $('.left-sidebar.sidebar').width();
  const width = $(window).width() - sidebar;
  $('.gworks-evt-pageHeader').css('width', width);

  $(window).on('scroll', function () {
    if ($(window).scrollTop() > 10) {
      $('.gworks-evt-pageHeader, .gworks-evt-right-panel').addClass('active');
    } else {
      $('.gworks-evt-pageHeader, .gworks-evt-right-panel').removeClass('active');
    }
  });

  setTimeout(function () {
    const tempHeight = $('.gworks-evt-pageHeader').height();
    const topMargin = tempHeight + 15;
    $('.gworks-evt-pageWrapper').css('padding-top', topMargin);
    $(window).scrollTop(0);
  }, 1500);
}

},{"../../js/medialibrary.popup":8,"./data":1,"./files":2,"./section":6,"./ui":7}],2:[function(require,module,exports){
module.exports = {

  setup: function () {
    const thisFiles = this;

    require('../../js/medialibrary.popup').addFiles({
      fnAddFile: function (newfile) {
        const files = require('../../js/medialibrary.popup').fetchFiles();

        for (const file of files) {
          if (file.id === newfile.id) {
            window.$gworks.core.onWarning('File already Added');
            return;
          }
        }

        files.push(newfile);
        thisFiles.render(files);
      }
    });
  },

  render: function (fileArr) {
    if (typeof fileArr === 'undefined' || fileArr == null || fileArr.length === 0) {
      return;
    }

    require('../../js/medialibrary.popup').renderFiles({
      files: fileArr,
      fnDelete: function (id) {
      }
    });
  }
}
;

},{"../../js/medialibrary.popup":8}],3:[function(require,module,exports){
module.exports = {

  setup: function () {
    $('#gworks-evt-am').on('click', '.gworks-item-add', add);
    $('#gworks-evt-am').on('click', '.gworks-item-delete', del);
  },

  addMinute: function (el) {
    const li = el.closest('li');
    li.find('.gworks-evt-minute-block').toggle();
    li.find('.gworks-item-minute').toggleClass('active');
    li.find('.gworks-evt-minute-block textarea').focus();
  },

  getData: function (el) {
    const files = [];

    el.find('.gworks-evt-agendafile').each(function () {
      if ($('#gworks-evt-am-form').hasClass('activecitizen') === true && $(this).attr('gworks-evt-official') === 'official') {
        return;
      }
      files.push({ filename: $(this).attr('gworks-evt-title'), usetype: $(this).attr('gworks-evt-official') });
    });
    const item = {
      type: 'agenda-item',
      value: el.find('.gworks-evt-agenda textarea').val(),
      minute: el.find('.gworks-evt-minute').val(),
      files: files
    };
    if (el.find('.gworks-evt-minute').val() !== '') {
      item.minute = window.$gworks.form.getMentions().getMentionValue(el.find('.gworks-evt-mentions'));
    }
    return item;
  },

  render: function (li, item) {
    if (item.value !== undefined) {
      li.find('ul.gworks-evt-itemlist').append($('#item-template').html());
      const lastLi = li.find('ul.gworks-evt-itemlist li:last');
      lastLi.find('.gworks-evt-agenda textarea').val(item.value);
      lastLi.find('.gworks-evt-minute').val(item.minute);

      if (item.files) {
        for (const file of item.files) {
          lastLi.find('.gworks-evt-agenda-files-block').append(`<div class="gworks-evt-agenda-file ${file.usetype === 'official' ? 'officialOnly' : ''}"><a target="_blank" class="gworks-evt-agendafile" gworks-evt-official="${file.usetype}" href="${window.$gworks.core.getMediaFileUrl(file.filename)}" class="text-info" data-toggle="tooltip" data-placement="bottom" gworks-evt-title="${file.filename}" title="${file.filename} ${file.usetype === 'official' ? '(city only)' : ''}">${file.usetype === 'official' ? '<i class="far fa-info-circle mr-1"></i>' : ''} ${file.filename}</a><i class="fal fa-times text-danger gworks-evt-agenda-files-remove" title="remove this file" aria-hidden="true"></i></div>`);
        }
      }
      if (item.minute !== '') {
        lastLi.find('.gworks-evt-minute-block').show();
        lastLi.find('.gworks-item-minute').hide();
      }
    }

    setupSortable();
  }

};


function del (event) {
  event.stopImmediatePropagation();
  const thisEl = $(this);

  window.$gworks.core.confirmDelete({
    title: 'Confirm Item Removal',
    content: 'Do you wish to remove this item?',
    btnConfirmLabel: 'Remove',
    fnConfirm: function (m) {
      window.$gworks.core.standardModal().close();
      thisEl.closest('li').remove();
    }
  });
}


function add (event) {
  event.stopImmediatePropagation();
  $(this).closest('li').find('ul.gworks-evt-itemlist').append($('#item-template').html());
  window.$gworks.form.getMentions().renderMention('.gworks-evt-mentions');
  setupSortable();
}


function setupSortable () {
  $('#gworks-evt-am .sortable-items').sortable({
    placeholder: 'ui-state-highlight',
    connectWith: '.sortable-items',
    handle: '.gworks-evt-sortable-grabber',
    dropOnEmpty: true,
    cursor: 'move',
    axis: 'y'
  });
}

},{}],4:[function(require,module,exports){
window.$gworks.core.queueForPageLoad(pageSetup);

function pageSetup () {
  ($('#gworks-evt-am-form').attr('type') === 'minutes') ? setupMinutesEditor() : setupAgendaEditor();

  if (window.$gworks.core.isPublicNoticesEnabled()) {
    $('#tab_public_notices').removeClass('disableItem');
  } else {
    $('#tab_public_notices').css('pointer-events', 'none');
  }

  if (window.$gworks.core.isAgendasMinutesEnabled()) {
    $('#tab_agendas_minutes').removeClass('disableItem');
  } else {
    $('#tab_agendas_minutes').css('pointer-events', 'none');
  }
}


function setupMinutesEditor () {
  $('.gworks-page-publish-minutes').on('click', function (event) {
    event.stopImmediatePropagation();
    publishMinutes();
  });
  $('.gworks-page-unpublish-minutes').on('click', function (event) {
    event.stopImmediatePropagation();
    unpublishMinutes();
  });

  $('.gworks-page-agenda').on('click', function (event) {
    event.stopImmediatePropagation();
    window.location = `am-editor-agenda.html?cms_meeting.id=${$('#gworks-evt-am-form').data('messId')}`;
  });

  $('#gworks-evt-am').on('click', '.gworks-item-minute', function (event) {
    event.stopImmediatePropagation();
    require('./item').addMinute($(this));
  });

  $('.gworks-page-preview-minute').on('click', function (event) {
    $('#gworks-evt-am-form').addClass('activecitizen');
    event.stopImmediatePropagation();
    require('./produce').previewMinute(require('./data').fetch());
  });

  setupCommon();

  loadMeeting(function (data) {
    if (data['cms_meeting.agenda_published_fl'] === false) {
      window.location = `am-editor-agenda.html?cms_meeting.id=${data['cms_meeting.id']}`;
    }
  });
}

function setupAgendaEditor () {
  require('./section').setup();

  $('.gworks-page-clone').on('click', function (event) {
    event.stopImmediatePropagation();
    cloneMeeting();
  });

  $('.gworks-page-preview-agenda').on('click', function (event) {
    $('#gworks-evt-am-form').addClass('activecitizen');
    event.stopImmediatePropagation();
    require('./produce').previewAgenda(require('./data').fetch());
  });

  $('.gworks-page-publish').on('click', function (event) {
    event.stopImmediatePropagation();
    publishAgenda();
  });

  $('.gworks-page-minutes').on('click', function (event) {
    event.stopImmediatePropagation();
    window.location = `am-editor-minutes.html?cms_meeting.id=${$('#gworks-evt-am-form').data('messId')}`;
  });

  setupCommon();
  loadMeeting();
}


function setupCommon () {
  require('./files').setup();

  $('.gworks-page-save').on('click', function (event) {
    event.stopImmediatePropagation();
    require('./data').save();
  });

  $('.gworks-page-delete').on('click', function (event) {
    event.stopImmediatePropagation();
    deleteMeeting();
  });

  $('.gworks-page-archive').on('click', function (event) {
    event.stopImmediatePropagation();
    archiveMeeting();
  });

  $('.gworks-evt-txt-download').on('click', function (event) {
    event.stopImmediatePropagation();
    require('./produce').generateTxt(require('./data').fetch());
  });

  require('./item').setup();

  window.$gworks.form.init('#gworks-evt-am-form');

  $('#gworks-evt-am').on('click', '.gworks-evt-agenda-files-remove', removeAgendaFile);
  $('#gworks-evt-am').on('click', '.gworks-evt-agenda-file-upload', addAgendaFile);

  require('./data').setupStickyBar();
}


function deleteMeeting () {
  const messId = $('#gworks-evt-am-form').data('messId');
  if (messId == null) {
    return;
  }

  window.$gworks.core.confirmDelete({
    title: 'Confirm Meeting Removal',
    content: 'Do you wish to remove this meeting?',
    btnConfirmLabel: 'Remove',
    fnConfirm: function (m) {
      window.$gworks.core.standardModal().close();

      window.$gworks.api.deleteSecure({
        uri: `/cms/secure/city/meeting/${messId}`,
        fnSuccess: function (data) {
          window.location = 'am.html';
        },
        fnError: function (data) {
          window.$gworks.core.onWarning(data);
        }
      });
    }
  });
}


function cloneMeeting () {
  const messId = $('#gworks-evt-am-form').data('messId');
  if (messId == null) {
    return;
  }

  window.$gworks.core.confirmDelete({
    title: 'Confirm Meeting Clone',
    content: 'Are you sure you wish to clone this meeting?',
    btnConfirmLabel: 'Clone',
    fnConfirm: function (m) {
      window.$gworks.core.standardModal().close();
      $('#gworks-evt-am-form').data('messId', null);
      $('input[name=cms_meeting\\.template_fl]').prop('checked', false);
      $('.gworks-evt-blank-on-clone').val('');
      $('.gworks-evt-publish').hide();
      $('.gworks-page-publish').show();
      $('.gworks-evt-updatedts').html('');
      $('.gworks-page-delete').hide();
      window.$gworks.core.updateSubTitle('Clone');
    }
  });
}


function loadMeeting (fnCallback) {
  const messId = window.$gworks.api.getUriParam('cms_meeting.id');
  if (messId != null && Number(messId) > 0) {
    window.$gworks.core.loadingOn();
    window.$gworks.api.getSecure({
      uri: `/cms/secure/city/meeting/${messId}`,
      fnSuccess: function (data) {
        $('#gworks-evt-am-form').data('messId', messId);
        require('./data').set(data);
        window.$gworks.core.appendTitle(data['cms_meeting.title']);

        loadUserData();

        if (fnCallback) {
          fnCallback(data);
        }
        window.$gworks.core.loadingOff();
      },
      fnError: function (data) {
        window.$gworks.core.onWarning(data);
        window.location = 'am.html';
      }
    });
  } else {
    $('.gworks-page-clone, .gworks-page-delete').hide();
    window.$gworks.core.appendTitle('New Meeting');
    initializeTemplate();
  }
}


function publishAgenda () {
  const formData = require('./data').fetch();
  if (formData != null) {
    window.$gworks.core.confirmDelete({
      title: 'Confirm Publishing Agenda',
      content: 'By clicking Publish, you are making this agenda available to the public',
      btnConfirmLabel: 'Publish Agenda',
      fnConfirm: function (m) {
        window.$gworks.core.standardModal().close();
        formData['cms_meeting.archived_fl'] = false;
        formData['cms_meeting.agenda_published_fl'] = true;
        formData['cms_meeting.agenda_published_dt'] = moment().format('YYYY-MM-DD');
        require('./data').save(formData);
      }
    });
  }
}


function archiveMeeting () {
  const formData = require('./data').fetch();
  if (formData != null) {
    window.$gworks.core.confirmDelete({
      title: 'Confirm Archive Meeting',
      content: 'By clicking Archive, you are removing this from the public',
      btnConfirmLabel: 'Archive Meeting',
      fnConfirm: function (m) {
        window.$gworks.core.standardModal().close();
        formData['cms_meeting.agenda_published_fl'] = false;
        formData['cms_meeting.agenda_published_dt'] = null;
        formData['cms_meeting.minutes_published_fl'] = false;
        formData['cms_meeting.minutes_published_dt'] = null;
        formData['cms_meeting.archived_fl'] = true;
        require('./data').save(formData);
      }
    });
  }
}


function loadUserData () {
  window.$gworks.api.postSecure({
    uri: '/core/secure/city/admin/employee/list',
    fnSuccess: function (data) {
      const items = [];
      for (const user of data.data) {
        if (user['city_employee_person.publicprofile_fl']) {
          items.push({
            uid: user['person.id'],
            name: user['person.display_name'],
            value: user['city_employee_person.nickname']
          });
        }
      }
      window.$gworks.form.getMentions().init('.gworks-evt-mentions', items);
    }
  });
}


function publishMinutes () {
  const formData = require('./data').fetch();
  if (formData != null) {
    window.$gworks.core.confirmDelete({
      title: 'Confirm Publishing Minutes',
      content: 'By clicking Publish, you are confirming that your governing body has approved Minutes for publication',
      btnConfirmLabel: 'Publish Minutes',
      fnConfirm: function (m) {
        window.$gworks.core.standardModal().close();
        formData['cms_meeting.minutes_published_fl'] = true;
        formData['cms_meeting.minutes_published_dt'] = moment().format('YYYY-MM-DD');
        require('./data').save(formData);
      }
    });
  }
}


function unpublishMinutes () {
  const formData = require('./data').fetch();
  if (formData != null) {
    window.$gworks.core.confirmDelete({
      title: 'Confirm Unpublishing Minutes',
      content: 'By clicking Unpublish you are removing the minutes from public view and placing them back in draft form. They will remain in draft form until you click Publish Minutes.',
      btnConfirmLabel: 'Unpublish Minutes',
      fnConfirm: function (m) {
        window.$gworks.core.standardModal().close();

        const messId = $('#gworks-evt-am-form').data('messId');
        window.$gworks.api.putSecure({
          uri: `/cms/secure/city/meeting/${messId}/unpublish`,
          fnSuccess: () => {
            window.$gworks.core.onSuccess('successfully unpublished!');
            $('.gworks-page-publish, .gworks-page-publish-minutes').show();
            $('.gworks-page-unpublish-minutes').addClass('d-none');
            $('.gworks-evt-publish').hide();
          },
          fnError: () => {
            window.$gworks.core.onError('Something went wrong!');
          }
        });
      }
    });
  }
}


function initializeTemplate () {
  const templateId = window.$gworks.api.getUriParam('template.id', null);
  const templateDt = window.$gworks.api.getUriParam('template.dt', null);

  if (templateDt != null) {
    $('#gworks-evt-am-form').find('input[name=cms_meeting\\.date]').val(templateDt);
  }

  if (templateId != null && Number(templateId) > 0) {
    window.$gworks.api.getSecure({
      uri: `/cms/secure/city/meeting/${Number(templateId)}`,
      fnSuccess: function (data) {
        for (const section of data['cms_meeting.data']) {
          for (const item of section.items) {
            item.minute = '';
          }
        }

        data['cms_meeting.files'] = null;
        data['cms_meeting.meeting_ts'] = null;
        data['cms_meeting.template_fl'] = false;
        data['cms_meeting.archived_fl'] = false;
        data['cms_meeting.agenda_published_fl'] = false;
        data['cms_meeting.minutes_published_fl'] = false;

        require('./data').set(data);
      },
      fnError: function (data) {
        window.$gworks.core.onWarning(data);
      }
    });
  }
}

function removeAgendaFile () {
  $(this).closest('.gworks-evt-agenda-file').remove();
}

function addAgendaFile () {
  const thisInst = $(this);
  require('../../js/medialibrary.popup').showPopup({
    contentBlock: 'medialibrary-custom-popup-block',
    filter: 'agenda',
    fnOnInsertHtml: function (html) {
      thisInst.closest('.gworks-evt-item-block').find('.gworks-evt-agenda-files-block').append(`<div class="gworks-evt-agenda-file">${html}<i class="fal fa-times text-danger gworks-evt-agenda-files-remove" title="remove this file" aria-hidden="true"></i></div>`);
      if (thisInst.closest('.gworks-evt-item-block').find('.gworks-evt-agendafile:last').attr('gworks-evt-official') === 'official') {
        thisInst.closest('.gworks-evt-item-block').find('.gworks-evt-agenda-file:last').addClass('officialOnly');
      }
    }
  });
}

},{"../../js/medialibrary.popup":8,"./data":1,"./files":2,"./item":3,"./produce":5,"./section":6}],5:[function(require,module,exports){
module.exports = {

  getHtmlAgenda: function (data) {
    return getHtml('#render-agenda-template', data);
  },

  getHtmlMinute: function (data) {
    return getHtml('#render-minute-template', data);
  },

  previewAgenda: function (data) {
    if (data == null) {
      return;
    }
    $('#gworks-evt-am-form').removeClass('activecitizen');
    window.$gworks.core.standardModal().open({
      title: 'Preview Agenda',
      content: getHtml('#render-agenda-template', data),
      btnCancelLabel: 'Close',
      fnOnLoad: function (jqModalBody) {
        $(jqModalBody).find('.gworks-pdf-download').attr('href', `${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/pdf/agenda/${window.$gworks.api.getUriParam('cms_meeting.id', null)}.pdf`);
      }
    });
  },

  previewMinute: function (data) {
    if (data == null) {
      return;
    }
    $('#gworks-evt-am-form').removeClass('activecitizen');
    window.$gworks.core.standardModal().open({
      title: 'Preview Minutes',
      content: getHtml('#render-minute-template', data),
      btnCancelLabel: 'Close',
      fnOnLoad: function (jqModalBody) {
        $(jqModalBody).find('.gworks-pdf-download').attr('href', `${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/pdf/minute/${window.$gworks.api.getUriParam('cms_meeting.id', null)}.pdf`);
      }
    });
  },

  generateTxt: function (data) {
    if (data == null) {
      return;
    }

    const html = getTxtHtml('#render-minute-txt-template', data);

    const downloadEle = document.createElement('a');
    downloadEle.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(html));
    downloadEle.setAttribute('download', `${data['cms_meeting.title']}.txt`);

    document.body.appendChild(downloadEle);
    downloadEle.click();
    document.body.removeChild(downloadEle);
  }
};

function wrapLine (data, lineSize) {
  if (data) {
    data = covertDataToName(data);
    const wordsArr = data.split(' ');
    const wordsLen = wordsArr.length;
    const lineData = [];
    let currentLine = '';
    for (let i = 0; i < wordsLen; i++) {
      if (currentLine.length + wordsArr[i].length > lineSize) {
        lineData.push(currentLine);
        currentLine = '';
      } else {
        currentLine += wordsArr[i] + ' ';
      }
    }
    if (currentLine !== '') {
      lineData.push(currentLine);
    }
    return lineData.join('\n').trim();
  }
}

function covertDataToName (data) {
  return data.replace(/@\[([^\]]+)\]\(([^ )]+)\)/g, function (val, name, id) {
    return name;
  });
}

function getTxtHtml (template, data) {
  data['cms_meeting.data'] = JSON.parse(data['cms_meeting.data']);
  data['cms_meeting.files'] = JSON.parse(data['cms_meeting.files']);

  const mData = flattenScope(data);

  for (const data of mData.cms_meeting.data) {
    data.items = data.items.map(item => {
      item = Object.assign(item, { minute: wrapLine(item.minute, 120), value: wrapLine(item.value, 120) });
      return item;
    });
  }

  mData.cms_meeting.category = window.$gworks.lookup.getLabelForId('agenda_category', mData.cms_meeting.category_ref_type_id);
  mData.cms_meeting.cityId = window.$gworks.lookup.getCityCode();
  mData.cms_meeting.cityName = window.$gworks.core.getCityDisplayName();
  mData.cms_meeting.meetingId = 0;
  mData.cms_meeting.meetingDate = window.$gworks.core.renderDateLong(mData.cms_meeting.meeting_ts);
  mData.cms_meeting.meetingTime = window.$gworks.core.renderTime(mData.cms_meeting.meeting_ts);

  const html = Mustache.render($(template).html(), mData.cms_meeting).trim().replace(/\t/g, '');
  return html;
}


function getHtml (template, data) {
  data['cms_meeting.data'] = JSON.parse(data['cms_meeting.data']);
  data['cms_meeting.files'] = JSON.parse(data['cms_meeting.files']);

  const mData = flattenScope(data);

  for (const data of mData.cms_meeting.data) {
    data.items = data.items.filter(v => typeof v.value !== 'undefined');

        data.items = data.items.map(item => {
      const minutes = window.$gworks.form.getMentions().covertDataToLink(item.minute, function (val, name, id) {
        return `<a target="_blank" href="${window.$gworks.lookup.getDomainPage()}/${id}_official.html">@${name}</a>`;
      });
      const agendafiles = [];
      if (item.files) {
        for (const f of item.files) {
          agendafiles.push(`<div><a target="_blank" href="${window.$gworks.core.getMediaFileUrl(f.filename)}">${f.filename}</a></div>`);
        }
      }
      item = Object.assign(item, { value: item.value !== undefined ? item.value.replace(/\n/g, '<br>').replace(/\s\s/g, '&ensp;&ensp;') : '', minute: minutes !== '' ? minutes.replace(/\n/g, '<br>').replace(/\s\s/g, '&ensp;&ensp;').replace(/\s\s/g, '&ensp;&ensp;') : '', agendafiles: agendafiles.length > 0 ? `<div class="agenda_files clearfix">${agendafiles.join('')}</div>` : '' });
      return item;
    });
  }

  mData.cms_meeting.category = window.$gworks.lookup.getLabelForId('agenda_category', mData.cms_meeting.category_ref_type_id);
  mData.cms_meeting.cityId = window.$gworks.lookup.getCityCode();
  mData.cms_meeting.meetingId = 0;
  mData.cms_meeting.meetingDate = window.$gworks.core.renderDateLong(mData.cms_meeting.meeting_ts);
  mData.cms_meeting.meetingTime = window.$gworks.core.renderTime(mData.cms_meeting.meeting_ts);

  for (const f of mData.cms_meeting.files) {
    f.fileUrl = window.$gworks.core.getMediaFileUrl(f.name);
  }

  const html = Mustache.render($(template).html(), mData.cms_meeting).trim().replace(/\t/g, '');

  for (const f of mData.cms_meeting.files) {
    delete f.fileUrl;
  }

  const metaData = [];
  metaData.push(`<script type="text/x-gworks" id="page-title">${mData.cms_meeting.title}</script>`);
  metaData.push(`<script type="text/x-gworks" id="page-summary">${mData.cms_meeting.location}</script>`);

  data['cms_meeting.data'] = JSON.stringify(data['cms_meeting.data']);
  data['cms_meeting.files'] = JSON.stringify(data['cms_meeting.files']);
  return metaData.join('') + html;
}


function flattenScope (data) {
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

},{}],6:[function(require,module,exports){
module.exports = {

  setup: function () {
    $('.gworks-section-add').on('click', add);
    $('#gworks-evt-am').on('click', '.gworks-section-delete', del);
  },

  getData: function (el) {
    const section = {
      type: 'section',
      title: el.find('.gworks-evt-title').length === 1 ? el.find('.gworks-evt-title').text() : el.find('input[type=text]').val(),
      items: []
    };

    el.find('.gworks-evt-itemlist li').each(function () {
      const item = require('./item').getData($(this));
      section.items.push(item);
    });

    return section;
  },

  render: function (section) {
    $('#gworks-evt-am').append($('#section-template').html());

    const li = $('#gworks-evt-am li:last');
    li.find('input[type=text]').val(section.title);
    li.find('.gworks-evt-title').text(section.title);

    for (const item of section.items) {
      require('./item').render(li, item);
    }
    setupSortable();
  }

};


function del (event) {
  event.stopImmediatePropagation();
  const thisEl = $(this);

  window.$gworks.core.confirmDelete({
    title: 'Confirm Section Removal',
    content: 'Do you wish to remove this section?',
    btnConfirmLabel: 'Remove',
    fnConfirm: function (m) {
      window.$gworks.core.standardModal().close();
      thisEl.closest('li').remove();
    }
  });
}


function add (event) {
  event.stopImmediatePropagation();
  $('#gworks-evt-am').append($('#section-template').html());
  setupSortable();
}


function setupSortable () {
  $('#gworks-evt-am').sortable({
    placeholder: 'ui-state-highlight',
    handle: '.gworks-evt-sortable-grabber',
    cursor: 'move',
    axis: 'y'
  });
  $('#gworks-evt-am').disableSelection();
}

},{"./item":3}],7:[function(require,module,exports){
module.exports = {

  setup: function (data) {
    const agendaMode = window.location.pathname.indexOf('am-editor-minutes.html') === -1;

    $('.gworks-evt-pdf-download').attr('gworks-id', data['cms_meeting.id']);
    $('.gworks-evt-pdf-download').attr('gworks-typeid', agendaMode ? 300 : 301);

    if (agendaMode) {
      if (data['cms_meeting.agenda_published_fl'] === true) {
        $('.gworks-page-publish').hide();
        $('.gworks-evt-publish, .gworks-page-agenda-publish').show();

        $('.gworks-evt-agenda_published_dt').text(`on ${window.$gworks.core.renderDateLongUtc(data['cms_meeting.agenda_published_dt'])}`);
        $('.gworks-page-publish, .gworks-page-publish-minutes').hide();

        $('.gworks-evt-publish, .gworks-page-minutes').show();
        $('.gworks-item-minute, .gworks-evt-saveastemplate').hide();
        $('button.gworks-page-preview-agenda').html('View Agenda');
      } else {
        $('.gworks-page-publish').show();
        $('.gworks-evt-publish, .gworks-page-minutes').hide();
      }

      $('.gworks-evt-pdf-download').attr('gworks-uri', `/cms/public/city/${window.$gworks.core.getCityCode()}/agenda/pdf/${data['cms_meeting.id']}/`);
    } else {
      if (data['cms_meeting.minutes_published_fl'] === true) {
        $('.gworks-evt-minutes_published_dt').text(`on ${window.$gworks.core.renderDateLongUtc(data['cms_meeting.minutes_published_dt'])}`);
        $('.gworks-page-publish, .gworks-page-publish-minutes').hide();

        if (moment().isBefore(moment(data['cms_meeting.minutes_published_dt']).add(2, 'days'))) {
          $('.gworks-page-unpublish-minutes').removeClass('d-none');
        }

        $('button.gworks-page-preview-minute').html('View Minutes');

        $('.gworks-evt-publish').show();
      }

      $('.gworks-evt-pdf-download').attr('gworks-uri', `/cms/public/city/${window.$gworks.core.getCityCode()}/minutes/pdf/${data['cms_meeting.id']}/`);
    }

    if (data['cms_meeting.agenda_published_fl'] === true || data['cms_meeting.minutes_published_fl'] === true) {
      $('#gworks-evt-am-form .gworks-page-delete').hide();
      $('#gworks-evt-am-form .gworks-page-archive').show();
    } else {
      $('#gworks-evt-am-form .gworks-page-archive').hide();
    }

    (data['cms_meeting.archived_fl'] === true) ? $('.gworks-evt-archive').show() : $('.gworks-evt-archive').hide();
  }
}
;

},{}],8:[function(require,module,exports){
module.exports = {

  fetchFiles: function (selector) {
    selector = selector || '.gworks-evt-media-files';

    const files = [];
    $(selector).find('.gworks-evt-file-block').each(function () {
      files.push({
        name: $(this).attr('gworks-evt-file-name'),
        id: $(this).attr('gworks-evt-file-id'),
        size: $(this).attr('gworks-evt-file-size'),
        type: $(this).attr('gworks-evt-file-type')
      });
    });

    return files;
  },


  addFiles: function (options) {
    options.addSelector = options.addSelector || '.gworks-page-add-files';
    $(document).on('click', options.addSelector, function () {
      showPopup(options);
    });
  },


  renderFiles: function (options) {
    const fileTemplate = $('#gworks-medialibrary-file-template').html();
    if (typeof fileTemplate === 'undefined') {
      const thisInst = this;
      $.get('/plugin/cms/common/snippet-mediafile-template.html', function (responseText, textStatus) {
        $('body').append($('<div>', {
          id: 'gworks-medialibrary-file-template',
          style: 'display: none'
        }));
        $('#gworks-medialibrary-file-template').html(responseText);
        thisInst.renderFiles(options);
      });
      return;
    }

    options.selector = options.selector || '.gworks-evt-media-files';
    if (options.files) {
      $(options.selector).empty();

      for (const f of options.files) {
        const html = Mustache.render(fileTemplate, {
          fileurl: f.url ? f.url : window.$gworks.core.getMediaFileUrl(f.name),
          fileclass: renderImageIcon(f.type),
          name: f.name,
          type: f.type,
          size: f.size,
          id: f.id
        });

        $(options.selector).append(html);
        const el = $(options.selector).find('.gworks-evt-img-block:last');

        if (options.fnDelete) {
          el.find('.gworks-evt-img-remove').on('click', function () {
            deleteFile(options.fnDelete, $(this).closest('.gworks-evt-img-block'));
          });
        } else {
          el.find('.gworks-evt-img-remove').remove();
        }
      }
    }
  },

  showPopup: function (options) {
    showPopup(options);
  }
};


function showPopup (options) {
  options.selector = options.selector || '#gworks-evt-standardModal';
  let isNew = '';
  if (options.selector) { isNew = true; }
  options.contentBlock = options.contentBlock || 'medialibrary-popup-block';
  window.$gworks.core.standardModal(isNew).open({
    title: options.title || 'Media Library',
    btnCancelShow: options.btnCancelShow || false,
    btnCancelLabel: options.btnCancelLabel || 'Cancel',
    selector: options.selector,
    content: `<div class='col-12 crm-citizen gworks-evt-files rightFilter' id='${options.contentBlock}'></div>`,
    fnOnLoad: function (jqModalBody) {
      $(options.selector).addClass('gworks-evt-MediaLibrary mediaModal');
      $(`${options.selector} .modal-content`).css('height', $(window).height() * 0.8);

      if (options.filter === 'pages') {
        window.$gworks.plugin.renderSnippet({
          plugin: 'cms',
          uri: 'common/snippet-mediapage.html',
          content: `#${options.contentBlock}`,
          fnSuccess: function () {
            window.$gworks.plugin.get('cms').getFile().getPageDataCardList('.gworks-evt-files', options);
          }
        });
      } else if (options.filter === 'agenda') {
        window.$gworks.plugin.renderSnippet({
          plugin: 'cms',
          uri: 'common/snippet-media-agenda.html',
          content: `#${options.contentBlock}`,
          fnSuccess: function () {
            window.$gworks.plugin.get('cms').getFile().getFileDataCardList('.gworks-evt-files', options);
          }
        });
      } else {
        window.$gworks.plugin.renderSnippet({
          plugin: 'cms',
          uri: 'common/snippet-mediafiles.html',
          content: `#${options.contentBlock}`,
          fnSuccess: function () {
            if (options.filter) {
              $(`#${options.contentBlock}`).find('.gworks-evt-media-filter').attr('filter-val', options.filter);
            }
            window.$gworks.plugin.get('cms').getFile().getFileDataCardList('.gworks-evt-files', options);
          }
        });
      }
    },
    fnOnClose: function () {
      $('#gworks-evt-standardModal').removeClass('gworks-evt-MediaLibrary mediaModal modal-confirmation');
      $('.modal-content').css('height', '');
    }
  });
}


function deleteFile (fnDelete, elBlock) {
  window.$gworks.core.confirmDelete({
    content: 'Do you really want to remove this file?',
    btnConfirmLabel: 'Delete',
    fnConfirm: function (jqModalBody) {
      elBlock.remove();
      fnDelete(elBlock.attr('gworks-evt-img-id'));
      window.$gworks.core.standardModal().close();
    }
  });
}


function renderImageIcon (fileType) {
  let fclass = 'fa-file text-info';
  if (fileType.indexOf('image') !== -1) {
    fclass = 'fa-file-image text-primary';
  } else if (fileType.indexOf('spreadsheet') !== -1) {
    fclass = 'fa-file-excel text-success';
  } else if (fileType.indexOf('word') !== -1) {
    fclass = 'fa-file-word text-info';
  } else if (fileType.indexOf('pdf') !== -1) {
    fclass = 'fa-file-pdf text-danger';
  }
  return fclass;
}

},{}]},{},[4]);
