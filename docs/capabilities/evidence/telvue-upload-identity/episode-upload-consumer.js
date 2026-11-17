  function populateNewEpisodeForm(xhr, firstAssetName) {
    if (window.location.href.indexOf('episodes/new') >= 0) {
      var mediaId = $.parseJSON(xhr.responseText).medium_id;
      var assetName = firstAssetName.substr(0, firstAssetName.indexOf('.'));
      assetName = assetName.replace('_', ' ');

      if ($.trim($('#episode_medium_attributes_title').val()) == '') $('#episode_medium_attributes_title').val(assetName);
      if ($.trim($('#episode_medium_attributes_short_summary').val()) == '') $('#episode_medium_attributes_short_summary').val(assetName);

      window.location.replace('./'); // Redirect one level up, back to Episodes index page.
    }
  }

  function addNewEpisodeFormData(data) {
    if (window.location.href.indexOf('episodes/new') >= 0) {
      if ($.trim($('#episode_medium_attributes_title').val()) != '') data.append('episode[medium_attributes][title]', $.trim($('#episode_medium_attributes_title').val()));
      if ($.trim($('#episode_medium_attributes_short_summary').val()) != '') data.append('episode[medium_attributes][short_summary]', $.trim($('#episode_medium_attributes_short_summary').val()));
      if ($.trim($('#episode_medium_attributes_episode_identifier').val()) != '') data.append('episode[medium_attributes][episode_identifier]', $.trim($('#episode_medium_attributes_episode_identifier').val()));
    }
  }
