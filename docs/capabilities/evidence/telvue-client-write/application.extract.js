var PlaylistItems = {
  originalOrder: null,
  playlistItemsTable: null,
  organizationId: null,
  collectionId: null,
  durationUrl: null,

  addSortableListenersToDataGrid: function() {
    if (PlaylistItems.playlistItemsTable.length) {
      PlaylistItems.playlistItemsTable.disableSelection();
      PlaylistItems.playlistItemsTable.sortable({
        axis: 'y',
        cursor: 'move',
        items: 'tr.sortable-row',
        update: function(event, ui) {
          AppWide.flashNotice('Remember to click "Save Order" when finished reordering.');
        }
      });
    }
  },

  addListenerToSaveOrderButton: function() {
    $('body.playlist_items-index').on('click', 'a[data-action="save-order"]', function(e){
      AppWide.clearFlashMessaging();
      PlaylistItems.reorderPlaylistItems();
    });
  },

  orderedPlaylistItemIds: function() {
    // jQuery sortable has a function that gathers ids from DOM, but this only
    // works if the sortable drag-n-drop listeners are triggered
    var results = new Array();
    $('tr.sortable-row').each(function(i, val){ results.push($(val).attr('id').split('_')[2]) });
    return results;
  },

  changeInOrdering: function(currentOrder) {
    for (var i = 0; i < currentOrder.length; ++i) {
      if (currentOrder[i] !== PlaylistItems.originalOrder[i]) return true;
    }
    return false;
  },

  reorderPlaylistItems: function() {
    var currentOrder = PlaylistItems.orderedPlaylistItemIds();
    if (!PlaylistItems.changeInOrdering(currentOrder)) {
      // There was no change to the ordering
      AppWide.flashWarning('Order was not changed. Nothing to save.');
      return;
    }

    Datagrid.showDatagridLoader();

    var playlistId = parseInt($('input#playlist_id').val());

    $.ajax({
      type: 'post',
      data: { playlist_item: currentOrder },
      url: '/playlists/'+ playlistId + '/reorder',
      success: function(data, textStatus, jqXHR) {
        $.get('/playlists/' + playlistId + '/playlist_items.json', function(jsonData){
          var tdSequenceNumbers = $('td.sequence_numbers');
          tdSequenceNumbers.each(function(index){
            $(this).text(jsonData.playlist_items[index].sequence_number);
          });
          Datagrid.hideDatagridLoader();
          AppWide.flashNotice('Playlist items successfully reordered.');
        });
      }
    });
  },

  addListenerToReorderSelect: function() {
    $('body.playlist_items-index').on('change', 'select[data-action="reorder-playlist-items-by-preset"]', function(){
      var selectedOption = $(this).val();
      $.getScript(window.location.pathname + '?ordering=' + selectedOption, function(){
        AppWide.flashNotice('Remember to click "Save Order" when finished reordering.');
      });
    });
  },

  addPlaylistDurationToIndexView: function() {
    if (PlaylistItems.durationUrl != null) {
      $.get(
        PlaylistItems.durationUrl,
        function(json){
          $('th#playlist_duration_in_seconds_text').html(json.duration_in_seconds);
        },
        'json'
      );
    }
  }

};

$(document).ready(function() {
  if ($('body').hasClass('playlist_items-index')) {
    PlaylistItems.originalOrder = PlaylistItems.orderedPlaylistItemIds();
    PlaylistItems.playlistItemsTable = $("table#playlist_item_data tbody");

    PlaylistItems.addSortableListenersToDataGrid();
    PlaylistItems.addListenerToSaveOrderButton();
    PlaylistItems.addListenerToReorderSelect();
    PlaylistItems.addPlaylistDurationToIndexView();

    MediaLibrary.initMediaLibrary({
      organizationId: PlaylistItems.organizationId,
      collectionId: PlaylistItems.collectionId,
      onSelect: MediaLibrary.selectForBulkPost,
      onMultiSubmit: MediaLibrary.createCollectionItemsFromMedia
    });
  }

  $('body.playlist_items-index').on('datagrid-reloaded', '#datagrid', function(){
    PlaylistItems.playlistItemsTable = $('table#playlist_item_data tbody');
    PlaylistItems.addSortableListenersToDataGrid();
    PlaylistItems.addPlaylistDurationToIndexView();
  });
});
var Playlists = {
  organizationId: null,

  lookupPlaylistDurationText: function() {
    var playlistTRs = $('tbody tr.result');
    $.each(playlistTRs, function(index, tr){
      var playlistId = $(tr).data('playlist-id');
      if (playlistId != undefined) {
        $.get(
          '/organizations/'+ Playlists.organizationId +'/playlists/'+ playlistId +'.json',
          function(json){
            $(tr).find('span.duration_in_seconds_text').html(json.duration_in_seconds);
          },
          'json'
        );
      }

    });

  }
};

document.addEventListener("DOMContentLoaded", function() {
  const playlistIndex = document.querySelectorAll('body.playlists-index');

  if (playlistIndex.length !== 0) {
    Playlists.lookupPlaylistDurationText();
  }
});


// ----- selected vendor function boundary -----

$('#datagrid_library').on('click', "button[data-action='bulk-create-playlist-items']", function(e) {
            $.ajax({
              url: '/bulk/playlists/' + PlaylistLibrary.selectedId + '/playlist_items/create',
              type: 'post',
              dataType: 'json',
              data: { medium_ids: mediumIds },
              success: function(data, textStatus, jqXHR) {
                AppWide.processFlashResponse(data);
                $.getScript(window.location.pathname);
                Shadowbox.close();
              },
              error: function() {
                AppWide.flashError('Could not create the playlist items due to a server error.');
                Shadowbox.close();
              }
            });
          });



// ----- selected vendor function boundary -----

function uploadFiles(files, options) {
    if(options['maxUploadCount'] && options['maxUploadCount'] > 0 && files.length > options['maxUploadCount']) {
      return validationFailure(0, 'Uploaded files', 'A maximum of ' + options['maxUploadCount'] + ' files can be uploaded at one time. Please reduce the number and try again.');
    }
    if(!options['allowMultipleMedia'] && files.length > 1) {
      return validationFailure(0, 'Uploaded files', 'Please upload only one video. Multiple files are allowed only if they are part of a DVD.');
    }

    var isResumable = (resumableSupported && $('#chk_resumable').is(':checked'));

    $.each(files, function(id, file) {
      options.uploadParams.js_uuid = options.userId + '-' + MD5(file.name);
      // the Rails controller will check to see if there's an existing TrackedActivity that isn't completed
      // if there is, it will not make another one on this ajax post call

      $.post(
        '/historical_data/track_upload',
        { js_uuid: options.uploadParams.js_uuid, resumable: isResumable }
      );

      chunkStart[id] = 0;
      chunkEnd[id] = 0;

      var validator = Medium.mediaFileValidator(file.name, file.size, options);

      if (validator.isValid()) {
        firstAssetName = file.name;
        prepareFormData(id, file, 'files[]', options.fileUrl, options);
      } else {
        validationFailure(id, validator.fileName, validator.errors());
      }
    });
  }



// ----- selected vendor function boundary -----

function prepareFormData(id, file, fileParam, url, options, batchName) {
    addBar(id, '#panel .scrollbar #progress_container');
    $('.scrollbar').scrollbar('repaint');

    var data = new FormData(); // FormData object. Only modern browsers support it: FF, Chrome, Safari.

    if ($.isArray(file)) {
      $.each(file, function(id, f) {
        data.append(fileParam, f);
      });
    } else {
      data.append(fileParam, file);
    }

    addCsrfToken(data);

    addNewEpisodeFormData(data);

    if (options.uploadParams) {
      for(var key in options.uploadParams) {
        var value = options.uploadParams[key];
        if(typeof(value) === 'object') {
          for(var key2 in value) {
            data.append(key + '[' + key2 + ']', value[key2]);
          }
        } else data.append(key, value);
      }
    }

    if ($.isArray(file)) {
      filenames[id] = ((batchName) ? batchName : file);
    } else {
      filenames[id] = ((batchName) ? batchName : file.name);
    }

    if (resumableSupported && !options.devEnv && $('#chk_resumable').is(':checked') && batchName === undefined) {
      $('#panel #blurb:not(:contains("Upload is resumable."))').append(' Upload is resumable.');
      resumableUpload(id, file, url, options);
    } else {
      upload(id, data, url, options);
    }
  }

  function upload(id, data, url, options) {
    var xhr = new XMLHttpRequest();

    xhr.addEventListener('error', function(event) { xhrError(xhr) }, false);
    xhr.addEventListener('readystatechange', function(event) { uploadReadyState(xhr, id, options) }, false);
    xhr.upload.addEventListener('progress', function(event) {
      updateProgress(id, event.lengthComputable ? event.loaded / event.total : 0, filenames[id]);
    }, false);
    xhr.upload.addEventListener('error', uploadError, false);

    xhr.open('POST', url);
    xhr.setRequestHeader('Accept', 'application/json');
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

    // xhr.withCredentials = true;

    xhr.send(data);
  }

  function resumableUpload(id, file, url, options) {
    url += '.json?resumable=true';
    if (options.series_id) url += '&series_id=' + options.series_id;

    if (options.uploadParams) {
      for(var key in options.uploadParams) {
        var value = options.uploadParams[key];
        if(typeof(value) === 'object') {
          for(var key2 in value) {
            url += '&' + key + '[' + key2 + ']=' + value[key2];
          }
        } else url += '&' + key + '=' + value;
      }
    }

    window.BlobBuilder = window.MozBlobBuilder || window.WebKitBlobBuilder || window.BlobBuilder;
    var FILE_SIZE = file.size;
    var bytesUploaded = 0;
    var isFinalChunk;
    var chunk;

    var sendChunk = function() {
      if (chunkStart[id] == 0 && chunkEnd[id] == 0) { // Calc first chunk.
        calcNextChunkRanges(id, FILE_SIZE, xhr);
      }

      if ('slice' in file) {
        chunk = file.slice(chunkStart[id], chunkEnd[id] + 1);
      } else if ('webkitSlice' in file) {
        chunk = file.webkitSlice(chunkStart[id], chunkEnd[id] + 1);
      } else if ('mozSlice' in file) {
        chunk = file.mozSlice(chunkStart[id], chunkEnd[id] + 1);
      } else {
        // Browser doesn't support chunking.
        return false;
      }

      var xhr = new XMLHttpRequest();
      xhr.addEventListener('readystatechange', function(event) { resumableReadyState(xhr, id) }, false);
      xhr.addEventListener('error', function(event) { xhrError(xhr) }, false);
      xhr.upload.addEventListener('error', uploadError, false);

      xhr.open('POST', url);

      // Resumable chunks must be synchronous, because the "next chunk" calculation depends upon what
      // Nginx returns in the Range header or the previous chunk, and because we must be able
      // to stop all chunks from being sent when one request fails.  We can't simply
      // use the `async = false` 3rd param on open() because, although that succeeds in uploading
      // the chunks, it blocks the entire UI while doing so [JS being single-threaded].
      // So we leave XHR in its default async mode, but achieve synchronicity with a
      // recursive function. Now the UI works and chunks are properly strung together.
      xhr.setRequestHeader('Accept', 'application/json');
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      xhr.setRequestHeader('Content-Disposition', 'attachment; filename="' + encodeURI(file.name) + '"');
      xhr.setRequestHeader('Content-Type', 'application/octet-stream');
      xhr.setRequestHeader('Session-Id', options.userId + '-' + MD5(file.name));
      xhr.setRequestHeader('X-Content-Range', 'bytes ' + chunkStart[id] + '-' + chunkEnd[id] + '/' + FILE_SIZE);
      // X-Content-Range:
      //   * Is always 1 byte less than actual Content-Length sent, even the final chunk.
      //   * Never overlap. Subsequent chunk starts 1 byte after end of last chunk.
      // slice(), mozSlice(), webkitSlice():
      //   * These determine Content-Length.
      //   * Start of subsequent chunk and End of last are identical.

      xhr.send(chunk);

      function resumableReadyState(xhr, id) {
        if (xhr.readyState == 4) {
          if (xhr.status == 200 || xhr.status == 201) {
            bytesUploaded = calcNextChunkRanges(id, FILE_SIZE, xhr);
            isFinalChunk = (xhr.getResponseHeader('Range') === null);

            if (isFinalChunk) {
              uploadSuccess(id, xhr);
              showSummary(options, xhr);
            } else {
              updateProgress(id, bytesUploaded / FILE_SIZE, filenames[id]);
              sendChunk(); // Recurse
            }
          } else {
            uploadFailure(id, xhr);
            showSummary(options, xhr);
            return false; // Break out of loop. Don't send any more chunks.
          }
        }
      }
    };

    sendChunk(); // Start upload.
  }

  function uploadReadyState(xhr, id, options) {
    // Callback to handle asynchronous-upload completion (non-resumable).
    // Fires every time XHR State changes, which is 4 times throughout the
    // life cycle of a Request.
    // The readyState property returns a value from 0 to 4:
    //   0: request not initialized
    //   1: server connection established
    //   2: request received
    //   3: processing request
    //   4: request finished and response is ready
    if (xhr.readyState == 4) {
      if (xhr.status == '202') delayedJobNotification = true;

      if (xhr.status == '200' || xhr.status == '201' || xhr.status == '202') {
        uploadSuccess(id, xhr);
      } else {
        uploadFailure(id, xhr);
      }
      showSummary(options, xhr);
    }
  }

  function uploadSuccess(id, xhr) {
    inProgress--;
    succeeded++;
    successBar(id, filenames[id]);
    // Intentionally no scrollbar repaint here. Success bars cannot have extra vertical space.
  }

  function uploadFailure(id, xhr) {
    inProgress--;
    failed++;
    var errMsg;

    if (xhr.status == 422) {
      // 422 HTTP error is 'Unprocessable Entity' and is validation failure in Rails.
      errors = $.parseJSON(xhr.responseText).errors;
      errMsg = errors ? ('Error: ' + errors.join(', ')) : "Error queuing file for processing.";
    } else {
      // Unexpected error. Display HTTP status text.
      errMsg = xhr.statusText;
    }
    errorBar(id, '#panel .scrollbar #progress_container', filenames[id], errMsg);
    $('.scrollbar').scrollbar('repaint'); // Do not remove this. Scrollbar must be repainted after failures only.
    // Failure bars can have more vertical space because of error messaging below them. Success bars can't.
  }

  function validationFailure(id, fileName, errMsg) {
    inProgress--;
    failed++;

    errorBar(id, '#panel .scrollbar #progress_container', fileName, errMsg);
    $('.scrollbar').scrollbar('repaint'); // Do not remove this.
  }

  function openPanel(callback) {
    var windowHeight = document.documentElement.clientHeight;
    var panelHeight = $('#panel').height();
    $("#panel").css({ 'top': windowHeight / 2 - panelHeight / 2 });

    $('#panel #close').click(function(e) {
      e.preventDefault();
      closePanel();
    });

    $('#panel_background').css({
      'opacity': '0.85',
      '-moz-opacity': '0.85',
      'filter': 'alpha(opacity=85)'
    });
    $('#panel_background').show();
    $('#panel').show(0, callback);
  }

  function closePanel() {
    $('#panel_background').fadeOut('fast');
    $('#panel').fadeOut('fast');
  }

  function addBar(id, containerId) {
    var html = '<div id="progress_total' + id + '" class="progress_total" style="float: left;">';
    html += '  <span class="progress"></span>';
    html += '</div>';
    html += '<div id="percent' + id + '" class="percent hint">0%</div>';
    html += '<div class="clear"></div>';
    $(containerId).append(html);
  }

  function successBar(id, fileName) {
    updateProgress(id, 1.0, fileName);
    $('#progress_total' + id + ' .progress').addClass('progress_success');
    $('#percent' + id).hide();
  }

  function errorBar(id, container, fileName, errMsg) {
    removeBar(id);
    if (fileName && fileName.length > 35) fileName = fileName.substring(0, 35) + '&#8230;';
    var html = '<div id="progress_total' + id + '" class="progress_total progress_error">';
    html += 'Failed:&nbsp;<span>' + fileName + '</span>';
    html += '</div>';
    if(errMsg && errMsg.forEach){
      errMsg.forEach(function(message){
          html += '<p class="hint">' + message + '</p>';
      });
    } else {
      html += '<p class="hint">' + errMsg + '</p>';
    }
    html += '<div class="clear"></div>';
    $(container).append(html);

    $('.scrollbar').scrollbar('repaint');
  }

  function removeBar(id) {
    $('#progress_total' + id + ' + p.hint').remove();
    $('#progress_total' + id + ' + div.clear').remove();
    $('#progress_total' + id).remove();
    $('#percent' + id).remove();
  }

  function updateProgress(id, amountComplete, filename) {
    var progressBarWidth = 238;
    var barWidth = parseInt(amountComplete * progressBarWidth) - 5;
    var bar = $('#progress_total' + id + ' .progress');
    bar.html(filename);
    if (barWidth > 20) {
    // if (barWidth > 20 && barWidth > bar.width()) {
      // Second half of the above condition prevents bar from going backwards.
      // An occasional chunked request happens out of sequence [which Nginx
      // allows and handles fine]. This caused bar jump.
      bar.width(barWidth);
    } else {
      bar.width(20);
    }
    $('#percent' + id).html( (amountComplete * 99).toFixed(1) + '%'); // Never show 100%.
  }

  function showSummary(options, xhr) {
    if (inProgress < 1) {
      var blurb = '';

      if (succeeded > 0) {
        if (succeeded > 1) {
          blurb += '<strong>' + succeeded + ' uploads succeeded.</strong> ';
        } else {
          blurb += '<strong>1 upload succeeded.</strong> ';
        }
        if (delayedJobNotification) {
          blurb += ' <br />DVD files have been queued for processing.';
          blurb += ' Visit the <a href="/activities">activity page</a>';
          blurb += ' to check processing status.';
        } else if (failed > 0) {
          blurb += '<strong>' + failed + ' failed.</strong><br />Refresh page or close this panel.';
          $('#panel #close').click(function(e) {
            // Rewire default Close event to refresh the page, so the user can see the ones that did upload.
            e.preventDefault();
            closePanel();
            options.onError();
            document.location.reload(true);
          });
          AppWide.notify('upload action stopped');
        }
      } else if (failed > 0) {
        blurb = 'Uploads failed.';
        $('#panel #close').click(function(e) {
          e.preventDefault();
          closePanel();
          document.location.reload(true);
        });
        AppWide.notify('upload action stopped');
      }

      $('#panel #blurb').html(blurb);

      if (failed == 0 && !delayedJobNotification) {
        var assetIds;
        try {
          assetIds = $.parseJSON(xhr.responseText).asset_ids;
        } catch(e) {
          assetIds = [];
        }
        if (assetIds) assetIds = assetIds.join(',');

        setTimeout(function() {
          closePanel();
          options.onComplete(assetIds, firstAssetName);
          populateNewEpisodeForm(xhr, firstAssetName);
        }, 1000);

        AppWide.notify('upload action stopped');
      }

      $('.scrollbar').scrollbar('repaint');
    }
  }

  function calcNextChunkRanges(id, fileSize, xhr) {
    // Chunks do not need to be in sequence.
    var bytesUploaded = 0;
    chunkStart[id] = 0;
    chunkEnd[id] = ((chunkStart[id] + CHUNK_SIZE < fileSize) ? (chunkStart[id] + CHUNK_SIZE) : (fileSize - 1));

    if (xhr !== undefined) {
      if (xhr.getResponseHeader('Range') && xhr.getResponseHeader('Range').match(/^\d+-\d+\/\d+/)) {
        // Response can be 0-66211/6621184,6554988-6621183/6621184, so the
        // end-of-string matcher ($) is intentionally omitted from RegEx.
        var holeStart = 0, holeEnd = 0;
        // Find first hole in ranges.
        $.each(xhr.getResponseHeader('Range').split(','), function(i, str) {
          var r = str.split('/')[0].split('-');
          var start = parseInt(r[0]);
          var end = parseInt(r[1]);
          bytesUploaded += end - start;

          if (holeEnd != 0) return true; // Restart loop

          if (start != 0) {
            holeEnd = start - 1;
          } else {
            holeStart = end + 1;
          }
        });
        chunkStart[id] = holeStart;
        if (holeEnd == 0) {
          holeEnd = fileSize - 1;
        }
        chunkEnd[id] = ((holeEnd - holeStart < CHUNK_SIZE) ? holeEnd : (chunkStart[id] + CHUNK_SIZE));
      } else {
        // Final chunk has no Range header.
        bytesUploaded = fileSize;
      }
    }
    return bytesUploaded;
  }

  function uploadError() {
    console.log('Unknown upload error.');
  }

  function xhrError(xhr) {
    console.log('Unknown AJAX error: ' + xhr.statusText);
  }

  function validateDvdFiles(files, options) {
    var totalSize = 0;
    $.each(files, function(i, file) {
      totalSize += file.size;
    });
    return Medium.mediaFileValidator('DVD.mpg', totalSize, options);
  }



// ----- vendor jquery-ujs CSRF prefilter -----
	// Make sure that every Ajax request sends the CSRF token
	function CSRFProtection(xhr) {
		var token = $('meta[name="csrf-token"]').attr('content');
		if (token) xhr.setRequestHeader('X-CSRF-Token', token);
	}
	if ('ajaxPrefilter' in $) $.ajaxPrefilter(function(options, originalOptions, xhr){ CSRFProtection(xhr) });
	else $(document).ajaxSend(function(e, xhr){ CSRFProtection(xhr) });
