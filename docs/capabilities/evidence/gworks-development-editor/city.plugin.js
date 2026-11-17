(function(){function r(e,n,t){function o(i,f){if(!n[i]){if(!e[i]){var c="function"==typeof require&&require;if(!f&&c)return c(i,!0);if(u)return u(i,!0);var a=new Error("Cannot find module '"+i+"'");throw a.code="MODULE_NOT_FOUND",a}var p=n[i]={exports:{}};e[i][0].call(p.exports,function(r){var n=e[i][1][r];return o(n||r)},p,p.exports,r,e,n,t)}return n[i].exports}for(var u="function"==typeof require&&require,i=0;i<t.length;i++)o(t[i]);return o}return r})()({1:[function(require,module,exports){
class PluginCMSCity extends window.$PlugInBaseClass {
  constructor () {
    super('plugincms');
  }

  getFile () {
    return require('./file');
  }

  importMediaPlugin () {
    return require('./medialibrary.plugin');
  }

  importPagePlugin () {
    return require('./pages.plugin');
  }

  getPages () {
    return require('./pages.select2');
  }

  getMediaLibraryPopup () {
    return require('./medialibrary.popup');
  }
}

window.$gworks.plugin.register(new PluginCMSCity());

},{"./file":2,"./medialibrary.plugin":3,"./medialibrary.popup":4,"./pages.plugin":5,"./pages.select2":6}],2:[function(require,module,exports){
module.exports = {
  getFileList: function (selector) {
    const thisInst = this;
    const config = getFileListConfig();
    thisInst.dtInst = window.$gworks.datatable.doConfig(`${selector} #mediafile`, config);

    $(selector).on('click', '.gworks-evt-file-add-new', function () {
      thisInst.__onFileUpload('.gworks-evt-upload-block');
    });

    $(selector).on('click', '.gworks-evt-file-delete', function () {
      thisInst.__deleteFile($(this).attr('cms_file.id'));
    });
  },

  getPageDataCardList: function (selector, options) {
    const thisInst = this;
    const config = getPageDataConfig();
    config.searching = true;

    if ($.fn.dataTable.isDataTable(`${selector} #mediafile`)) {
      $(`${selector} #mediafile`).DataTable().destroy();
    }

    thisInst.dtInst = window.$gworks.datatable.doConfig(`${selector} #mediafile`, config);

    if (options.fnOnInsertHtml) {
      $(options.selector).on('click', '.gworks-evt-file-row', function (e) {
        e.stopImmediatePropagation();
        $('.gworks-evt-a-tag').val($(this).find('.gworks-evt-page-popup-insert').attr('gworks-evt-page-name'));
        $('.gworks-evt-image-iframe a').attr('href', window.$gworks.lookup.getDomainPage() + $(this).find('.gworks-evt-page-popup-insert').attr('gworks-evt-page-url'));
        $('.gworks-evt-image-iframe a').attr('gworks-evt-link', $(this).find('.gworks-evt-page-popup-insert').attr('gworks-evt-page-url'));
        $('.gworks-evt-image-iframe a').attr('gworks-evt-file-name', $(this).find('.gworks-evt-page-popup-insert').attr('gworks-evt-page-name'));
        $('.gworks-evt-image-iframe a').removeClass('d-none');
        $('.gwoks-evt-tinymce-block').removeClass('d-none');
      });

      $(options.selector).on('click', '.gworks-evt-file-insert-editor', function (e) {
        e.stopImmediatePropagation();
        options.fnOnInsertHtml(`<a title="${$('.gworks-evt-a-tag').val()}" href="${options.pageLink !== '' ? window.$gworks.lookup.getDomainPage() : '/c/'}${$('.gworks-evt-image-iframe a').attr('gworks-evt-link')}">${$('.gworks-evt-image-iframe a').attr('gworks-evt-file-name')}</a>`);
        window.$gworks.core.standardModal().close(options);
      });
    }
    closeModel(options);
  },

  getFileDataCardList: function (selector, options) {
    const thisInst = this;
    const config = getFileDataConfig(options.filter);
    config.searching = true;

    if ($.fn.dataTable.isDataTable(`${selector} #mediafile`)) {
      $(`${selector} #mediafile`).DataTable().destroy();
    }

    thisInst.dtInst = window.$gworks.datatable.doConfig(`${selector} #mediafile`, config);

    $(selector).off().on('click', '.gworks-evt-file-add-new', function () {
      thisInst.__onFileUpload('.gworks-evt-upload-block');
    });

    if (options.fnOnInsertHtml && options.filter === 'agenda') {
      $(options.selector).off().on('click', '.gworks-evt-file-row', function (e) {
        $('.gworks-evt-a-tag').val($(this).find('.gworks-evt-file-popup-insert').attr('gworks-evt-file-name'));
        $('.gworks-evt-image-iframe a').attr('href', $(this).find('.gworks-evt-file-link').attr('href'));
        $('.gworks-evt-image-iframe a').attr('gworks-evt-link', $(this).find('.gworks-evt-file-link').attr('href'));
        $('.gworks-evt-image-iframe a').attr('gworks-evt-file-name', $(this).find('.gworks-evt-file-popup-insert').attr('gworks-evt-file-name'));
        $('#gworks-evt-filename').html($(this).find('.gworks-evt-file-popup-insert').attr('gworks-evt-file-name'));
        $('.gworks-evt-image-iframe a').removeClass('d-none');
        $('.gwoks-evt-tinymce-block').removeClass('d-none');
        $('.gworks-evt-upload-block').addClass('d-none');
      });
      $(options.selector).on('click', '.gworks-evt-file-insert-editor', function (e) {
        e.stopImmediatePropagation();
        options.fnOnInsertHtml(`<a target="_blank" class="gworks-evt-agendafile" gworks-evt-official="${$('input[name=fileuse]:checked').val()}" gworks-evt-title="${$('.gworks-evt-image-iframe a').attr('gworks-evt-file-name')}" title="${$('.gworks-evt-image-iframe a').attr('gworks-evt-file-name')} ${$('input[name=fileuse]:checked').val() === 'official' ? '(city only)' : ''}" data-placement="bottom" href="${window.$gworks.core.getMediaFileUrl($('.gworks-evt-image-iframe a').attr('gworks-evt-file-name'))}"> ${$('input[name=fileuse]:checked').val() === 'official' ? '<i class="far fa-info-circle mr-1"></i>' : ''} <span>${$('.gworks-evt-image-iframe a').attr('gworks-evt-file-name')}</span></a>`);
        window.$gworks.core.standardModal().close(options);
      });
      showUploadButton();
    } else {
      $('#mediafile').off().on('click', '.gworks-evt-file-row', function (e) {
        $(this).siblings('tr').removeClass('selected');
        $(this).addClass('selected');
        if (!$(e.target).hasClass('gworks-evt-preview')) {
          setFileData($(this).find('.gworks-evt-file-popup-insert'), options);
        }
      });
    }
    closeModel(options);
  },

  __deleteFile: function (fileId) {
    const thisInst = this;

    window.$gworks.core.confirmDelete({
      content: 'This process cannot be undone.',
      fnConfirm: function (jqModalBody) {
        window.$gworks.core.standardModal().close();
        window.$gworks.api.deleteSecure({
          uri: `/cms/secure/media/${fileId}/`,
          fnSuccess: function (data) {
            window.$gworks.core.onSuccess('successfully deleted');
            window.$gworks.datatable.reload(thisInst.dtInst);
          },
          fnError: function (data) {
            window.$gworks.core.onWarning(data);
          }
        });
      }
    });
  },

  __onFileUpload: function (selector) {
    const fileToUpload = $(selector).find('[name=file]')[0].files;
    if (fileToUpload.length === 0) {
      window.$gworks.core.onWarning('please select a file to upload');
      return;
    }

    const postData = {
      'cms_file.filename': '',
      'cms_file.mime_type': '',
      'cms_file.size_kb': ''
    };
    const thisInst = this;
    let allowedExt = 'gif|jpg|jpeg|png|pdf|doc|docx|ppt|pptx|xls|xlsx';
    if ($(document).find('.gworks-evt-media-filter').attr('filter-val') === 'nonimages') {
      allowedExt = 'pdf|doc|docx|ppt|pptx|xls|xlsx';
    } else if ($(document).find('.gworks-evt-media-filter').attr('filter-val') === 'images') {
      allowedExt = 'gif|jpg|jpeg|png';
    }
    window.$gworks.api.uploadFile({
      url: '/cms/secure/media',
      postdata: postData,
      maxFileSize: 30000,
      allowedExt: allowedExt,
      file: fileToUpload[0],
      fnSuccess: function (e, data) {
        $(selector).find('[name=file]').val(null);
        window.$gworks.core.onSuccess('File Successfully Uploaded; Please wait a moment while we process it for it to appear', {
          timeOut: 4000,
          onHidden: function () {
            if (thisInst.dtInst) {
              window.$gworks.datatable.reload(thisInst.dtInst);
              setTimeout(function () {
                $('#gworks-evt-standardModal').find('.gworks-evt-file-popup-insert:first').click();
              }, 1200);
            }
          }
        });
      },
      fnError: function (data) {
        window.$gworks.core.onWarning(data.message);
      }
    });
  }
};

function getPageDataConfig () {
  return {
    url: '/cms/secure/page/list',
    filter: {},
    searching: false,
    featureExport: false,
    featureSchedule: false,
    featureFilter: true,
    featureSelect: false,
    order: [[1, 'desc']],
    createdRow: function (row, data, dataIndex) {
      $(row).addClass('gworks-evt-file-row');
    },
    columns: [
      {
        data: 'cms_page\\.title',
        searchable: true,
        orderable: true,
        render: function (data, type, row) {
          return ` <a class="pr-2 text-secondary" data-toggle="tooltip" data-placement="top" title="Click to Preview" target="_blank" cms_page.id='${row['cms_page.id']}'><span gworks-evt-page-url="${row['cms_page.page_uri']}" gworks-evt-page-name="${data}" class='pointer gworks-evt-page-popup-insert' data-toggle="tooltip" data-placement="top" title="Add this page">${data}</span></a>`;
        }
      },
      {
        data: 'cms_page\\.created_ts',
        class: 'text-align-center',
        orderable: true,
        render: function (data, type, row, meta) {
          if (type === 'display') {
            return window.$gworks.core.renderPersonCreateMod(row['person.create_person_display_name'], row['cms_page.created_ts']);
          } else {
            return row['cms_page.created_ts'];
          }
        }
      }
    ]
  };
}

function getFileDataConfig (fileFilter) {
  return {
    url: '/cms/secure/media/list',
    filter: {},
    searching: false,
    featureExport: false,
    featureSchedule: false,
    featureFilter: true,
    featureSelect: false,
    order: [[1, 'desc']],
    createdRow: function (row, data, dataIndex) {
      $(row).addClass('gworks-evt-file-row');
    },
    columns: [
      {
        data: 'cms_file\\.filename',
        searchable: true,
        orderable: true,
        render: function (data, type, row) {
          let filetype = '<i class="fa fa-file text-info" aria-hidden="true">';
          if (row['cms_file.mime_type'].indexOf('image') !== -1) {
            filetype = '<i class="fa fa-file-image text-primary" aria-hidden="true"></i>';
          } else if (row['cms_file.mime_type'].indexOf('spreadsheet') !== -1) {
            filetype = '<i class="fa fa-file-excel text-success" aria-hidden="true"></i>';
          } else if (row['cms_file.mime_type'].indexOf('word') !== -1) {
            filetype = '<i class="fa fa-file-word text-info" aria-hidden="true"></i>';
          } else if (row['cms_file.mime_type'].indexOf('pdf') !== -1) {
            filetype = '<i class="fa fa-file-pdf text-danger" aria-hidden="true"></i>';
          }

          return ` <a class="pr-2 text-secondary" data-toggle="tooltip" data-placement="top" title="Click to Preview" target="_blank" href='${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/media/${row['cms_file.filename']}' cms_file.id='${row['cms_file.id']}'>${fileFilter ? '' : '<i class="gworks-evt-preview far fa-eye" aria-hidden="true"></i>'}</a> ${filetype} <span gworks-evt-file-id="${row['cms_file.id']}" gworks-evt-file-size="${row['cms_file.size_kb']}" gworks-evt-file-type="${row['cms_file.mime_type']}" gworks-evt-file-name="${data}" class='pointer gworks-evt-file-popup-insert' data-toggle="tooltip" data-placement="top" title="Add this file">${data}</span>`;
        }
      },
      {
        data: 'cms_file\\.created_ts',
        class: 'text-align-center',
        orderable: true,
        render: function (data, type, row, meta) {
          if (type === 'display') {
            return window.$gworks.core.renderPersonCreateMod(row['person.create_person_display_name'], row['cms_file.created_ts']);
          } else {
            return row['cms_file.created_ts'];
          }
        }
      }
    ]
  };
}


function getFileListConfig () {
  return {
    url: '/cms/secure/media/list',
    filter: {},
    searching: true,
    featureExport: false,
    featureSchedule: false,
    featureFilter: true,
    filterInline: true,
    featureSelect: false,
    order: [[4, 'desc']],
    columns: [
      {
        data: 'cms_file\\.filename',
        render: function (data, type, row) {
          return `<a target="_blank" href='${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/media/${row['cms_file.filename']}' class='gworks-evt-file-inspects' cms_file.id='${row['cms_file.id']}'>${data}</a>`;
        },
        orderable: true,
        searchable: true
      },
      {
        data: 'cms_file\\.mime_type',
        orderable: true,
        searchable: true,
        render: function (data, type, row) {
          if (row['cms_file.mime_type'].indexOf('image') !== -1) {
            return '<i class="fa fa-file-image text-primary" aria-hidden="true"></i> Image';
          } else if (row['cms_file.mime_type'].indexOf('spreadsheet') !== -1) {
            return '<i class="fa fa-file-excel text-success" aria-hidden="true"></i> Excel';
          } else if (row['cms_file.mime_type'].indexOf('word') !== -1) {
            return '<i class="fa fa-file-word text-info" aria-hidden="true"></i> Word';
          } else if (row['cms_file.mime_type'].indexOf('pdf') !== -1) {
            return '<i class="fa fa-file-pdf text-danger" aria-hidden="true"></i> Pdf';
          } else {
            return '<i class="fa fa-file text-info" aria-hidden="true"></i>Other';
          }
        }
      },
      {
        data: 'cms_file\\.size_kb',
        class: 'text-align-right',
        orderable: true,
        render: window.$gworks.datatable.renderBlankIfNull
      },
      {
        data: 'cms_file\\.created_ts',
        class: 'text-align-center',
        orderable: true,
        render: function (data, type, row, meta) {
          if (type === 'display') {
            return window.$gworks.core.renderPersonCreateMod(row['person.create_person_display_name'], row['cms_file.created_ts']);
          } else {
            return row['cms_file.created_ts'];
          }
        }
      },
      {
        data: 'cms_file\\.id',
        class: 'text-align-center',
        render: function (data, type, row) {
          return `<a href='javascript:void(0)' class='gworks-evt-file-delete text-danger' title="delete this" cms_file.id='${row['cms_file.id']}'><i class="fa fa-trash" aria-hidden="true"></i></a>`;
        }
      }
    ]
  };
}

function setFileData (trobj, options) {
  if (options.fnAddFile) {
    options.fnAddFile({
      id: trobj.attr('gworks-evt-file-id'),
      size: trobj.attr('gworks-evt-file-size'),
      name: trobj.attr('gworks-evt-file-name'),
      type: trobj.attr('gworks-evt-file-type')
    });
    window.$gworks.core.standardModal().close(options);
  }

  if (options.fnOnInsertHtml) {
    $(document).find('.gworks-evt-img-size').change(function () {
      $('.gworks-evt-image-iframe img').attr('width', getImageSize());
    });
    $(options.selector).off().on('click', '.gworks-evt-file-insert-editor', function (e) {
      if (e.target.id !== 'button-media-page') {
        if (options.filter === 'images') {
          options.fnOnInsertHtml(`<img alt="${$('.gworks-evt-img-alt').val()}" width="${getImageSize()}" src="${$('.gworks-evt-image-iframe img').attr('src')}"></img>`);
        } else if (options.filter === 'nonimages') {
          options.fnOnInsertHtml(`<a title="${$('.gworks-evt-a-tag').val()}" width="${getImageSize()}" href="${$('.gworks-evt-image-iframe a').attr('href')}">${$('.gworks-evt-image-iframe a').attr('gworks-evt-file-name')}</a>`);
        }
        window.$gworks.core.standardModal().close(options);
      } 

          });

    $('.gwoks-evt-tinymce-block').removeClass('d-none');
    $('.gworks-evt-upload-block').addClass('d-none');

    if (options.filter === 'images') {
      $('.gworks-evt-image-iframe img').attr('src', `${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/media/${trobj.attr('gworks-evt-file-name')}`).attr('alt', trobj.attr('gworks-evt-file-name'));
      $('.gworks-evt-image-iframe img').removeClass('d-none');
      if ('pagetype' in options) {
        $('.gworks-evt-upload-inset').hide();
        $('.gworks-evt-settings').removeClass('d-none');
      } else {
        $('.gworks-evt-image-block').removeClass('d-none');
        $('.gworks-evt-img-alt').val(trobj.attr('gworks-evt-file-name'));
      }
    } else if (options.filter === 'nonimages') {
      $('.gworks-evt-a-tag').val(trobj.attr('gworks-evt-file-name'));

      $('.gworks-evt-image-iframe a').attr('href', `${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/media/${trobj.attr('gworks-evt-file-name')}`);
      $('.gworks-evt-image-iframe a').attr('gworks-evt-file-name', trobj.attr('gworks-evt-file-name'));
      $('.gworks-evt-image-iframe a').removeClass('d-none');
      $('.gworks-evt-file-block').removeClass('d-none');
    }

    showUploadButton();
  }
}

function showUploadButton () {
  $(document).find('.gworks-evt-show-upload').click(function () {
    $('.gwoks-evt-tinymce-block').addClass('d-none');
    $('.gworks-evt-upload-block').removeClass('d-none');
  });
}

function getImageSize () {
  const imgSize = $('.gworks-evt-img-size').val();
  if (imgSize === 'small') {
    return '128px;';
  } else if (imgSize === 'medium') {
    return '400px;';
  } else if (imgSize === 'large') {
    return '1080px;';
  } else {
    return '128px;';
  }
}

function closeModel (options) {
  $(options.selector).find('.close').click(function () {
    window.$gworks.core.standardModal().close(options);
  });

  $('.gworks-evt-standardModalCancel').click(function () {
    window.$gworks.core.standardModal().close(options);
  });
}

},{}],3:[function(require,module,exports){
(function () {
  let medialibrary = (function () {

    tinymce.PluginManager.add('medialibrary', function (editor, url) {
      let _dialog = false;
      const initData = {
        type: 'htmlpanel',
        html: ''
      };

      let _filesOptions = [initData];

      function _getDialogConfig () {
        return {
          title: 'Files',
          size: 'medium',
          body: {
            type: 'tabpanel',
            tabs: [
              {
                name: 'Files',
                title: 'Files',
                items: _filesOptions

              }]
          },
          onChange: function (dialogApi, details) {
            let data = dialogApi.getData();
            let isValid = false;
            for (const item in data) {
              if (item === 'file' && data[item].length > 0) {
                isValid = true;
                break;
              } else if (item !== 'file' && data[item]) {
                isValid = true;
                break;
              }
            }
            let toggle = isValid ? dialogApi.enable : dialogApi.disable;
            toggle('insert-button');
          },
          onSubmit: function (api) {
            const popupData = api.getData();

            for (let key in popupData) {
              if (popupData[key] === true) {
                const pagedata = key.split('/-|--|-/');
                if (pagedata[1] === 'file') {
                  editor.insertContent(`<a href="${window.configData.filesUrl}/city/${window.$gworks.core.getCityCode()}/media/${pagedata[0]}">${pagedata[0]}</a>`);
                }
              }
            }
            api.close();
          },
          onClose: function () {
            _filesOptions = [initData];
          },
          buttons: [
            {
              text: 'Close',
              type: 'cancel',
              onclick: 'close'
            },
            {
              text: 'Insert',
              type: 'submit',
              name: 'insert-button',
              primary: true,
              disabled: true
            }
          ]
        };
      }

      function _onAction () {
        _dialog = editor.windowManager.open(_getDialogConfig());

        _dialog.block('Loading...');

        setTimeout(function () {
          window.$gworks.api.postSecure({
            uri: '/cms/secure/media/list',
            fnSuccess: function (data) {
              _mediaOptions = [];

              for (const ref of data.data) {
                if (ref['cms_file.mime_type'].indexOf('image') === -1) {
                  const appendData = {
                    type: 'checkbox',
                    name: ref['cms_file.filename'] + '/-|--|-/file',
                    label: `<span>${ref['cms_file.filename']}</span>&nbsp; <span style="float:right" class="time">${moment(ref['cms_file.created_ts']).utc().format('L')}</span>`
                  };
                  _filesOptions.push(appendData);
                }
              }
              _dialog.redial(_getDialogConfig());

              _dialog.unblock();
            },
            fnError: function (data) {
              window.$gworks.core.onWarning(data);
            }
          });
        }, 1000);
      }
      editor.ui.registry.addButton('medialibrary', {
        text: 'Files',
        icon: 'bubbles',
        onAction: _onAction
      });

      editor.ui.registry.addMenuItem('medialibrary', {
        text: 'Files',
        context: 'insert',
        onAction: _onAction
      });
    });
  }());
})();

},{}],4:[function(require,module,exports){
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

},{}],5:[function(require,module,exports){
(function () {
  const pages = (function () {
    'use strict';

    tinymce.PluginManager.add('pages', function (editor, url) {
      let _dialog = false;
      const initData = {
        type: 'htmlpanel',
        html: ''
      };
      const _pageOptions = [initData];
      const _agendaOptions = [initData];
      const _noticeOptions = [initData];
      const _faqOptions = [initData];
      const _minutesOptions = [initData];

      function _getDialogConfig () {
        return {
          title: 'Pages',
          size: 'medium',
          body: {
            type: 'tabpanel',
            tabs: [
              {
                name: 'Pages',
                title: 'Pages',
                items: _pageOptions

              },
              {
                name: 'Public Notice',
                title: 'Public Notice',
                items: _noticeOptions

              },
              {
                name: 'Agenda',
                title: 'Agenda',
                items: _agendaOptions

              },
              {
                name: 'Minutes',
                title: 'Minutes',
                items: _minutesOptions

              },
              {
                name: 'FAQ',
                title: 'FAQ',
                items: _faqOptions

              }
            ]
          },
          onSubmit: function (api) {
            const popupData = api.getData();
            for (const key in popupData) {
              if (popupData[key] === true) {
                const pagedata = key.split('/-|--|-/');
                editor.insertContent(`<a href="/${pagedata[1]}">${pagedata[0]}</a>`);
              }
            }

            api.close();
          },
          buttons: [
            {
              text: 'Close',
              type: 'cancel',
              onclick: 'close'
            },
            {
              text: 'Insert',
              type: 'submit',
              primary: true,
              enabled: false
            }
          ]
        };
      }

      function _onAction () {
        _dialog = editor.windowManager.open(_getDialogConfig());

        if (_pageOptions.length === 1) {
          _dialog.block('Loading...');

          setTimeout(function () {
            window.$gworks.api.postSecure({
              uri: '/cms/secure/page/list',
              fnSuccess: function (data) {
                const searchItem = {
                  type: 'htmlpanel',
                  html: '<div class="gwork-evt-search-block"><input type="text" name="" class="form-control gworks-evt-kwtxt"><input type="button" class="btn btn-outline-secondary input-btn text-nowrap gworks-evt-popup-search" value="Search"></div>'
                };

                _faqOptions.push(searchItem);
                _noticeOptions.push(searchItem);
                _pageOptions.push(searchItem);
                _agendaOptions.push(searchItem);
                _minutesOptions.push(searchItem);

                for (const ref of data.data) {
                  const appendData = {
                    type: 'checkbox',
                    name: ref['cms_page.title'] + '/-|--|-/' + ref['cms_page.page_uri'],
                    label: `<div class="gworks-evt-checkbox-label" data-toggle="tooltip" data-placement="top" page-title="${ref['cms_page.title']}" title="${ref['cms_page.description']}"><span>${ref['cms_page.title']}</span> &nbsp; <span style="float:right" class="time">${moment(ref['cms_file.created_ts']).utc().format('L')}</span></div>`
                  };
                  if (ref['cms_page.body_definition_id'] === 1) {
                    _faqOptions.push(appendData);
                  }
                  if (ref['cms_page.body_definition_id'] === 2) {
                    _pageOptions.push(appendData);
                  }
                  if (ref['cms_page.body_definition_id'] === 3) {
                    _noticeOptions.push(appendData);
                  }
                  if (ref['cms_page.body_definition_id'] === 4) {
                    _agendaOptions.push(appendData);
                  }
                  if (ref['cms_page.body_definition_id'] === 5) {
                    _minutesOptions.push(appendData);
                  }
                }
                $(document).on('click', '.gworks-evt-popup-search', function () {
                  const searchKw = $(this).closest('.gwork-evt-search-block').find('.gworks-evt-kwtxt').val().toLowerCase();
                  if (searchKw !== '') {
                    $(document).find('.tox-checkbox').each(function () {
                      if ($(this).find('.gworks-evt-checkbox-label').attr('page-title').toLowerCase().includes(searchKw)) {
                        $(this).removeClass('d-none');
                      } else {
                        $(this).addClass('d-none');
                      }
                    });
                  } else {
                    $('.tox-checkbox').removeClass('d-none');
                  }
                });

                _dialog.redial(_getDialogConfig());

                _dialog.unblock();
              },
              fnError: function (data) {
                window.$gworks.core.onWarning(data);
              }
            });
          }, 1000);
        }
      }
      editor.ui.registry.addButton('pages', {
        text: 'Pages',
        onAction: _onAction
      });

      editor.ui.registry.addMenuItem('pages', {
        text: 'Pages',
        context: 'insert',
        onAction: _onAction
      });
    });
  }());
})();

},{}],6:[function(require,module,exports){
module.exports = {
  init: function (el) {
    const ajax = window.$gworks.api.postSecureParams({
      uri: '/cms/secure/page/list'
    });

    ajax.data = function (params) {
      return {
        search: {
          value: params.term
        },
        equals: {
          'cms_page.publish_fl': true
        },
        columns: [
          {
            data: 'cms_page.title',
            searchable: true
          },
          {
            data: 'cms_page.page_uri'
          }

        ],
        length: 20,
        start: 0
      };
    };

    ajax.processResults = function (serverResponse) {
      const s = { results: [] };
      for (const row of serverResponse.data) {
        s.results.push({
          id: row['cms_page.page_uri'],
          text: row['cms_page.title']
        });
      }
      return s;
    };

    $(el).find('.gworks-pages-to-list').select2({
      language: {
        searching: function () {
          return 'Searching...';
        }
      },
      ajax
    });
    $('.gworks-pages-to-list').on('select2:select', function (e) {
      tinymce.activeEditor.execCommand('mceInsertContent', false, `<a href="${window.$gworks.lookup.getDomainPage()}${$(this).val()}">${e.params.data.text}</a>`);
      $('.gworks-pages-to-list').val('').trigger('change');
    });
  }
}
;

},{}]},{},[1]);
