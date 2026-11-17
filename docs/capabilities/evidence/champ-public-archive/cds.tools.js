;

function CDSTools() {}


/*

*/
CDSTools.isDevSite = function(){
  var localURL = window.location.href;
  return ( (localURL.indexOf('devplay') > -1) || (localURL.indexOf('qcplay') > -1) );
}

/*

*/
CDSTools.logDebug = async function () {
  let args = Array.from(arguments);
  if(CDSTools.IS_DEBUG){
    args.unshift('DEBUG ::: cds.tools')
    console.log.apply(console, args);
  }
}

CDSTools.logError = async function () {
  let args = Array.from(arguments);
        args.unshift('viewlog')
  console.error.apply(console, args);
}

/*

*/
CDSTools.getQueryString = function()
{
    var vars = [], hash;
    var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
    for(var i = 0; i < hashes.length; i++){
        hash = hashes[i].split('=');
        vars.push(hash[0]);
        vars[hash[0]] = hash[1];
    }
    return vars;
}

/*

*/
CDSTools.getUserAgent = function()
{
  var userAgent = navigator.userAgent || navigator.vendor || window.opera;

  CDSTools.logDebug("UserAgent: " + userAgent);

  //if( userAgent.match( /iPad/i ) || userAgent.match( /iPhone/i ) || userAgent.match( /iPod/i ) )
  if(userAgent.match( /iPhone/i ) || userAgent.match( /iPod/i ) ) {
    return 'ios';
  } else if(userAgent.match( /iPad/i ) ) {
    return 'ipad';
  } else if( userAgent.match( /Android/i ) ) {
    return 'android';
  } else if( userAgent.match( /CrOS/i ) ) {
    return 'chromeos';
  } else {
    var is_chrome = navigator.userAgent.indexOf('Chrome') > -1;
    var is_explorer = navigator.userAgent.indexOf('MSIE') > -1;
    var is_firefox = navigator.userAgent.indexOf('Firefox') > -1;
    var is_safari = navigator.userAgent.indexOf("Safari") > -1;
    var is_opera = navigator.userAgent.toLowerCase().indexOf("op") > -1;
    if ((is_chrome)&&(is_safari)) {is_safari=false;}
    if ((is_chrome)&&(is_opera)) {is_chrome=false;}

    if(is_safari)
      return 'safari';
    else
      return 'desktop';
  }
}

/*

*/
CDSTools.getJSON = function(url, callback) //error, data
{
  //jQuery.support.cors = true;
  var output = '';
  var data = null;
  //$.support.cors = true;
  $.ajax(
  {
    //crossDomain: true,
    dataType: "json",
    url: url,
    data: data,
    // beforeSend: function(req){
    //   req.setRequestHeader('x-cdsreleasemode', (CDSTools.isDevSite() ? 'development' : 'notset'));
    // },
    xhrFields: {
      withCredentials: true
    },
    // headers: {
    //  //'Access-Control-Allow-Origin': '*',
    //  'x-cdsreleasemode': (CDSTools.isDevSite() ? 'development' : 'bloo')
    // },
    success: function(data)
    {
      callback(null, data);
    },
    fail: function( jqxhr, textStatus, error )
    {
      var err = textStatus + ", " + error;

      callback(err, null);
    },
    error: function(XMLHttpRequest, textStatus, errorThrown) {
      //console.log("CDSTools.getJSON - ERROR for:", url, "STATUS:", textStatus, "THROWN:", errorThrown);
      callback(textStatus, null);
    }
  });
}

/*

*/
CDSTools.getJSONWithData = function(url, data, isWithAuth) //error, data
{
  let headers = {};
  if(CDSTools.isDevSite()) headers['x-cdsreleasemode'] = 'development'; // <-- careful (this is okay since its just dev) but this WILL CAUSE options preflight. on. every. request.
  
  return new Promise( function (resolve, reject) {
    $.ajax({
      method: "GET",
      dataType: "json",
      url: url,
      data: data,
      xhrFields: {
        withCredentials: isWithAuth
      },
      headers: headers,
      success: function(data) {
        resolve(data);
      },
      fail: function( jqxhr, textStatus, error ) {
        var err = textStatus + ", " + error;
        console.error('getJSON ERROR', error);
        reject(err);
      },
      error: function(XMLHttpRequest, textStatus, errorThrown) {
        console.log("ERROR!!!! CDSTools.getJSON - ERROR for:", {url, textStatus, errorThrown, XMLHttpRequest});
        let errorMessage = textStatus;
        if(XMLHttpRequest && XMLHttpRequest.responseJSON)
          errorMessage = XMLHttpRequest.responseJSON;
        else if(XMLHttpRequest && XMLHttpRequest.responseText)
          errorMessage = XMLHttpRequest.responseText;
        reject(errorMessage);
      }
    });
  });
}

/*

*/
CDSTools.postJSON = function(url, data, isWithAuth)
{
  let headers = {};
  if(CDSTools.isDevSite()) headers['x-cdsreleasemode'] = 'development';
  
  return new Promise( function (resolve, reject) {
    $.ajax({
      method: "POST",
      dataType: "json",
      url: url,
      data: data,
      xhrFields: {
        withCredentials: isWithAuth
      },
      headers: headers,
      success: function(data) {
        resolve(data);
      },
      fail: function( jqxhr, textStatus, error ) {
        var err = textStatus + ", " + error;
        console.error('postJSON ERROR', error);
        reject(err);
      },
      error: function(XMLHttpRequest, textStatus, errorThrown) {
        console.log("ERROR!!!! CDSTools.postJSON - ERROR for:", {url, textStatus, errorThrown, XMLHttpRequest});
        let errorMessage = textStatus;
        if(XMLHttpRequest && XMLHttpRequest.responseJSON)
          errorMessage = XMLHttpRequest.responseJSON;
        else if(XMLHttpRequest && XMLHttpRequest.responseText)
          errorMessage = XMLHttpRequest.responseText;
        reject(errorMessage);
      }
    });
  });
}

/*

*/
CDSTools.getJSONQuick = function(url, callback, isWithCredentials = true) //error, data
{
  var output = '';
  var data = null;
  $.ajax(
  {
    dataType: "json",
    url: url,
    data: data,
    xhrFields: {
      withCredentials: isWithCredentials
    },
    timeout: 5000,
    success: function(data)
    {
      callback(null, data);
    },
    fail: function( jqxhr, textStatus, error )
    {
      var err = textStatus + ", " + error;

      callback(err, null);
    },
    error: function(XMLHttpRequest, textStatus, errorThrown) {
      callback(textStatus, null);
    }
  });
}

/*

*/
CDSTools.preventEnter = function(evt, obj, callbackEnter)
{  
  var keyCode = evt.which;
     
  if(keyCode >= 96 && keyCode <= 105)
    keyCode = keyCode - 48;
  
  var keychar = String.fromCharCode(keyCode);
  
  if (keyCode == 13) //enter key
  {
    evt.preventDefault();

    if(typeof(callbackEnter) == 'function')
      callbackEnter(obj);

    return false;
  }
  else
  {
    return true;
  }
}

/*

*/
CDSTools.encodeHTML = function(value)
{
  //create a in-memory div, set it's inner text(which jQuery automatically encodes)
  //then grab the encoded contents back out.  The div never exists on the page.
  return $('<div/>').text(value).html();
}

/*

*/
CDSTools.decodeHTML = function(value)
{

  return $('<div/>').html(value).text();
}

/*

*/
CDSTools.escapeHTML = function (text) 
{
  return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
}

/*

*/

CDSTools.arrayCompare = function (array1, array2)
{
  // let's attach the .compare method to Array's prototype to call it on any array 
  // NOPE, this screws up things on objects, etc later on.

  // if the other array is a falsy value, return
  if (!array1 && !array2)
    return true;

  if (!array1 || !array2)
    return false;

  // compare lengths - can save a lot of time
  if (array1.length != array2.length)
    return false;

  //for (var i = 0, l = array1.length; i < l; i++)
  for (var i in array1)
  {
    // Check if we have nested arrays
    if ((array1[i] instanceof Array && array2[i] instanceof Array) || (array1[i] instanceof Object && array2[i] instanceof Object))
    {
      // recurse into the nested arrays
      if (!CDSTools.arrayCompare(array1[i], array2[i]))
        return false;
    }
    else if (array1[i] != array2[i])
    {
      // Warning - two different object instances will never be equal: {x:20} != {x:20}
      return false;
    }
  }
  return true;
}

/*

*/
CDSTools.trimHeader = function (title)
{
  if (!title)
    title = '';

  title = title.trim();

  if (title.length < 1)
  {
    title = CONSTANTS['DisplayElement_EMPTYSTRING'];
  }
  else
  {
    var maxWidth = CONSTANTS['DisplayElement_ELEMENTCHARCOUNT'];

    if (title.length > maxWidth)
      title = title.substring(0, (maxWidth / 2)).trim() + "..." + title.substring(title.length - (maxWidth / 2)).trim();
  }
  return title;
}

/*

*/
CDSTools.trimTitleElement = function (title)
{
  if (!title)
    title = '';

  title = title.trim();

  if (title.length < 1)
  {
    title = CONSTANTS['DisplayElement_EMPTYSTRING'];
  }
  else
  {
    var maxWidth = CONSTANTS['DisplayElement_ELEMENTCHARCOUNT'];

    if (title.length > maxWidth)
      title = title.substring(0, (maxWidth / 2)).trim() + "..." + title.substring(title.length - (maxWidth / 2)).trim();
  }
  return title;
}

/*

*/
CDSTools.abbreviateString = function (title, len)
{
  if (!title)
    title = '';

  title = title.trim();

  if (title.length < 1)
  {
    title = CONSTANTS['DisplayElement_EMPTYSTRING'];
  }
  else
  {
    if (title.length > len)
      title = title.substring(0, (len / 2)).trim() + "..." + title.substring(title.length - (len / 2)).trim();
  }
  return title;
}

/*

*/
CDSTools.nl2br = function(text)
{
  if (text)
    return text.replace(new RegExp("\n", 'g'), "<br/>"); //return text.replace("\n", "<br/>");
  else
    return '';
}

/*

*/
CDSTools.arraySubstringMatcher = function(strs) 
{
  return function findMatches(q, cb) 
  {
    var matches, substrRegex;

    // an array that will be populated with substring matches
    matches = [];
 
    // regex used to determine if a string contains the substring `q`
    substrRegex = new RegExp(q, 'i');
 
    // iterate through the pool of strings and for any string that
    // contains the substring `q`, add it to the `matches` array
    $.each(strs, function(i, str)
    {
      if (substrRegex.test(str.title) || substrRegex.test(str.uuid))
      {
        // the typeahead jQuery plugin expects suggestions to a
        // JavaScript object, refer to typeahead docs for more info

        matches.push({ id:str.id, disp: '(' + str.uuid + ') ' + str.title });
      }
    });
    cb(matches);
  };
}

/*

*/
CDSTools.async = function(func, callback)
{
  setTimeout(function ()
  {
    func();
    if (callback)
    {
      callback(); 
    }
  }, 0);
}



/*

*/
CDSTools.taggedData = function(tag,data)
{
  this.LastUpdateUTC = new Date().toUTCString();
  this.Tag = tag;
  this.Data = data;
}



/*

*/
CDSTools.zeroPad = function(d)
{
  if (0 <= d && d < 10) return "0" + d.toString();
  if (-10 < d && d < 0) return "-0" + (-1 * d).toString();
  return d.toString();
}

Date.prototype.toMysqlFormat = function ()
{

  return this.getUTCFullYear() + "-" + CDSTools.zeroPad(1 + this.getUTCMonth()) + "-" + CDSTools.zeroPad(this.getUTCDate()) + " " + CDSTools.zeroPad(this.getUTCHours()) + ":" + CDSTools.zeroPad(this.getUTCMinutes()) + ":" + CDSTools.zeroPad(this.getUTCSeconds());
};


/*

*/
CDSTools.md5 = function (str)
{
  //  discuss at: http://phpjs.org/functions/md5/
  // original by: Webtoolkit.info (http://www.webtoolkit.info/)
  // improved by: Michael White (http://getsprink.com)
  // improved by: Jack
  // improved by: Kevin van Zonneveld (http://kevin.vanzonneveld.net)
  //    input by: Brett Zamir (http://brett-zamir.me)
  // bugfixed by: Kevin van Zonneveld (http://kevin.vanzonneveld.net)
  //  depends on: utf8_encode
  //   example 1: md5('Kevin van Zonneveld');
  //   returns 1: '6e658d4bfcb59cc13f96c14450ac40b9'

  var xl;

  var rotateLeft = function (lValue, iShiftBits)
  {
    return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits));
  };

  var addUnsigned = function (lX, lY)
  {
    var lX4, lY4, lX8, lY8, lResult;
    lX8 = (lX & 0x80000000);
    lY8 = (lY & 0x80000000);
    lX4 = (lX & 0x40000000);
    lY4 = (lY & 0x40000000);
    lResult = (lX & 0x3FFFFFFF) + (lY & 0x3FFFFFFF);
    if (lX4 & lY4)
    {
      return (lResult ^ 0x80000000 ^ lX8 ^ lY8);
    }
    if (lX4 | lY4)
    {
      if (lResult & 0x40000000)
      {
        return (lResult ^ 0xC0000000 ^ lX8 ^ lY8);
      } else
      {
        return (lResult ^ 0x40000000 ^ lX8 ^ lY8);
      }
    } else
    {
      return (lResult ^ lX8 ^ lY8);
    }
  };

  var _F = function (x, y, z)
  {
    return (x & y) | ((~x) & z);
  };
  var _G = function (x, y, z)
  {
    return (x & z) | (y & (~z));
  };
  var _H = function (x, y, z)
  {
    return (x ^ y ^ z);
  };
  var _I = function (x, y, z)
  {
    return (y ^ (x | (~z)));
  };

  var _FF = function (a, b, c, d, x, s, ac)
  {
    a = addUnsigned(a, addUnsigned(addUnsigned(_F(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  };

  var _GG = function (a, b, c, d, x, s, ac)
  {
    a = addUnsigned(a, addUnsigned(addUnsigned(_G(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  };

  var _HH = function (a, b, c, d, x, s, ac)
  {
    a = addUnsigned(a, addUnsigned(addUnsigned(_H(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  };

  var _II = function (a, b, c, d, x, s, ac)
  {
    a = addUnsigned(a, addUnsigned(addUnsigned(_I(b, c, d), x), ac));
    return addUnsigned(rotateLeft(a, s), b);
  };

  var convertToWordArray = function (str)
  {
    var lWordCount;
    var lMessageLength = str.length;
    var lNumberOfWords_temp1 = lMessageLength + 8;
    var lNumberOfWords_temp2 = (lNumberOfWords_temp1 - (lNumberOfWords_temp1 % 64)) / 64;
    var lNumberOfWords = (lNumberOfWords_temp2 + 1) * 16;
    var lWordArray = new Array(lNumberOfWords - 1);
    var lBytePosition = 0;
    var lByteCount = 0;
    while (lByteCount < lMessageLength)
    {
      lWordCount = (lByteCount - (lByteCount % 4)) / 4;
      lBytePosition = (lByteCount % 4) * 8;
      lWordArray[lWordCount] = (lWordArray[lWordCount] | (str.charCodeAt(lByteCount) << lBytePosition));
      lByteCount++;
    }
    lWordCount = (lByteCount - (lByteCount % 4)) / 4;
    lBytePosition = (lByteCount % 4) * 8;
    lWordArray[lWordCount] = lWordArray[lWordCount] | (0x80 << lBytePosition);
    lWordArray[lNumberOfWords - 2] = lMessageLength << 3;
    lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29;
    return lWordArray;
  };

  var wordToHex = function (lValue)
  {
    var wordToHexValue = '',
      wordToHexValue_temp = '',
      lByte, lCount;
    for (lCount = 0; lCount <= 3; lCount++)
    {
      lByte = (lValue >>> (lCount * 8)) & 255;
      wordToHexValue_temp = '0' + lByte.toString(16);
      wordToHexValue = wordToHexValue + wordToHexValue_temp.substr(wordToHexValue_temp.length - 2, 2);
    }
    return wordToHexValue;
  };

  var utf8_encode = function(string)
  {

    string = (string + '').replace(/\r\n/g, "\n").replace(/\r/g, "\n");

    var utftext = "";
    var start, end;
    var stringl = 0;

    start = end = 0;
    stringl = string.length;
    for (var n = 0; n < stringl; n++)
    {
      var c1 = string.charCodeAt(n);
      var enc = null;

      if (c1 < 128)
      {
        end++;
      } else if ((c1 > 127) && (c1 < 2048))
      {
        enc = String.fromCharCode((c1 >> 6) | 192) + String.fromCharCode((c1 & 63) | 128);
      } else
      {
        enc = String.fromCharCode((c1 >> 12) | 224) + String.fromCharCode(((c1 >> 6) & 63) | 128) + String.fromCharCode((c1 & 63) | 128);
      }
      if (enc != null)
      {
        if (end > start)
        {
          utftext += string.substring(start, end);
        }
        utftext += enc;
        start = end = n + 1;
      }
    }

    if (end > start)
    {
      utftext += string.substring(start, string.length);
    }

    return utftext;
  };

  var x = [],
    k, AA, BB, CC, DD, a, b, c, d, S11 = 7,
    S12 = 12,
    S13 = 17,
    S14 = 22,
    S21 = 5,
    S22 = 9,
    S23 = 14,
    S24 = 20,
    S31 = 4,
    S32 = 11,
    S33 = 16,
    S34 = 23,
    S41 = 6,
    S42 = 10,
    S43 = 15,
    S44 = 21;

  str = utf8_encode(str);
  x = convertToWordArray(str);
  a = 0x67452301;
  b = 0xEFCDAB89;
  c = 0x98BADCFE;
  d = 0x10325476;

  xl = x.length;
  for (k = 0; k < xl; k += 16)
  {
    AA = a;
    BB = b;
    CC = c;
    DD = d;
    a = _FF(a, b, c, d, x[k + 0], S11, 0xD76AA478);
    d = _FF(d, a, b, c, x[k + 1], S12, 0xE8C7B756);
    c = _FF(c, d, a, b, x[k + 2], S13, 0x242070DB);
    b = _FF(b, c, d, a, x[k + 3], S14, 0xC1BDCEEE);
    a = _FF(a, b, c, d, x[k + 4], S11, 0xF57C0FAF);
    d = _FF(d, a, b, c, x[k + 5], S12, 0x4787C62A);
    c = _FF(c, d, a, b, x[k + 6], S13, 0xA8304613);
    b = _FF(b, c, d, a, x[k + 7], S14, 0xFD469501);
    a = _FF(a, b, c, d, x[k + 8], S11, 0x698098D8);
    d = _FF(d, a, b, c, x[k + 9], S12, 0x8B44F7AF);
    c = _FF(c, d, a, b, x[k + 10], S13, 0xFFFF5BB1);
    b = _FF(b, c, d, a, x[k + 11], S14, 0x895CD7BE);
    a = _FF(a, b, c, d, x[k + 12], S11, 0x6B901122);
    d = _FF(d, a, b, c, x[k + 13], S12, 0xFD987193);
    c = _FF(c, d, a, b, x[k + 14], S13, 0xA679438E);
    b = _FF(b, c, d, a, x[k + 15], S14, 0x49B40821);
    a = _GG(a, b, c, d, x[k + 1], S21, 0xF61E2562);
    d = _GG(d, a, b, c, x[k + 6], S22, 0xC040B340);
    c = _GG(c, d, a, b, x[k + 11], S23, 0x265E5A51);
    b = _GG(b, c, d, a, x[k + 0], S24, 0xE9B6C7AA);
    a = _GG(a, b, c, d, x[k + 5], S21, 0xD62F105D);
    d = _GG(d, a, b, c, x[k + 10], S22, 0x2441453);
    c = _GG(c, d, a, b, x[k + 15], S23, 0xD8A1E681);
    b = _GG(b, c, d, a, x[k + 4], S24, 0xE7D3FBC8);
    a = _GG(a, b, c, d, x[k + 9], S21, 0x21E1CDE6);
    d = _GG(d, a, b, c, x[k + 14], S22, 0xC33707D6);
    c = _GG(c, d, a, b, x[k + 3], S23, 0xF4D50D87);
    b = _GG(b, c, d, a, x[k + 8], S24, 0x455A14ED);
    a = _GG(a, b, c, d, x[k + 13], S21, 0xA9E3E905);
    d = _GG(d, a, b, c, x[k + 2], S22, 0xFCEFA3F8);
    c = _GG(c, d, a, b, x[k + 7], S23, 0x676F02D9);
    b = _GG(b, c, d, a, x[k + 12], S24, 0x8D2A4C8A);
    a = _HH(a, b, c, d, x[k + 5], S31, 0xFFFA3942);
    d = _HH(d, a, b, c, x[k + 8], S32, 0x8771F681);
    c = _HH(c, d, a, b, x[k + 11], S33, 0x6D9D6122);
    b = _HH(b, c, d, a, x[k + 14], S34, 0xFDE5380C);
    a = _HH(a, b, c, d, x[k + 1], S31, 0xA4BEEA44);
    d = _HH(d, a, b, c, x[k + 4], S32, 0x4BDECFA9);
    c = _HH(c, d, a, b, x[k + 7], S33, 0xF6BB4B60);
    b = _HH(b, c, d, a, x[k + 10], S34, 0xBEBFBC70);
    a = _HH(a, b, c, d, x[k + 13], S31, 0x289B7EC6);
    d = _HH(d, a, b, c, x[k + 0], S32, 0xEAA127FA);
    c = _HH(c, d, a, b, x[k + 3], S33, 0xD4EF3085);
    b = _HH(b, c, d, a, x[k + 6], S34, 0x4881D05);
    a = _HH(a, b, c, d, x[k + 9], S31, 0xD9D4D039);
    d = _HH(d, a, b, c, x[k + 12], S32, 0xE6DB99E5);
    c = _HH(c, d, a, b, x[k + 15], S33, 0x1FA27CF8);
    b = _HH(b, c, d, a, x[k + 2], S34, 0xC4AC5665);
    a = _II(a, b, c, d, x[k + 0], S41, 0xF4292244);
    d = _II(d, a, b, c, x[k + 7], S42, 0x432AFF97);
    c = _II(c, d, a, b, x[k + 14], S43, 0xAB9423A7);
    b = _II(b, c, d, a, x[k + 5], S44, 0xFC93A039);
    a = _II(a, b, c, d, x[k + 12], S41, 0x655B59C3);
    d = _II(d, a, b, c, x[k + 3], S42, 0x8F0CCC92);
    c = _II(c, d, a, b, x[k + 10], S43, 0xFFEFF47D);
    b = _II(b, c, d, a, x[k + 1], S44, 0x85845DD1);
    a = _II(a, b, c, d, x[k + 8], S41, 0x6FA87E4F);
    d = _II(d, a, b, c, x[k + 15], S42, 0xFE2CE6E0);
    c = _II(c, d, a, b, x[k + 6], S43, 0xA3014314);
    b = _II(b, c, d, a, x[k + 13], S44, 0x4E0811A1);
    a = _II(a, b, c, d, x[k + 4], S41, 0xF7537E82);
    d = _II(d, a, b, c, x[k + 11], S42, 0xBD3AF235);
    c = _II(c, d, a, b, x[k + 2], S43, 0x2AD7D2BB);
    b = _II(b, c, d, a, x[k + 9], S44, 0xEB86D391);
    a = addUnsigned(a, AA);
    b = addUnsigned(b, BB);
    c = addUnsigned(c, CC);
    d = addUnsigned(d, DD);
  }

  var temp = wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d);

  return temp.toLowerCase();
};


