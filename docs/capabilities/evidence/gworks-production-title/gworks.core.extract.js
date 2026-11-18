// Original lines 70-116
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
// Original lines 215-285
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
// Original lines 1877-1930
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
// Original lines 2200-2230

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
