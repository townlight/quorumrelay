
                let assignableParams = {
            'model_type': 'meeting'
        }
        
        const vueMeetingForm = new Vue({
            el: '#meeting-form',
            mixins: [window.$datesMixin],
            data() {
                return {
                    loading: true,
                    page: 1,
                    meetingSections: {
                        meetingSummary: {
                            opened: false,
                            completed: false,
                            completedText: ''
                        },
                        dateAndTime: {
                            opened: false,
                            completed: false,
                            completedText: ''
                        },
                        videoAndCollaboration: {
                            opened: false,
                            completed: false,
                            completedText: ''
                        },
                        descriptionAndDetails: {
                            opened: true,
                            completed: false,
                            completedText: ''
                        },
                        invitees: {
                            opened: false,
                            completed: false,
                            completedText: ''
                        },
                        guests: {
                            opened: false,
                            completed: false,
                            completedText: ''
                        },
                    },
                    meetingTypes: {
                        singleMeeting: true,
                        multiDayMeeting: false,
                        recurringMeeting: false
                    },
                    showSearchResults: false,
                    calMonth: null,
                    calDate: null,
                    recurrenceStartText: '',
                    recurrenceEndText: '',
                    showVideo: false,
                    showInvitees: false,
                    showDateAndTime: false,
                    passcodeRequired: false,
                    durationText: [],
                    meetingTitles: JSON.parse('{}'),
                    recentGuests: [],
                    scheduler: false,
                    meetingDuration: '',
                    period: JSON.parse('{}'),
                    start: "4:45 pm",
                    end: "5:45 pm",
                    showTitle: false,
                    form: $form.make(JSON.parse('{}')),
                    formSubmitting: false,
                    formSubmittingNotify: false,
                    assignable_groups: [],
                    assignable_users: [],
                    edit: "1",
                    editType: "Meeting",
                    starting_date: "11/17/2026",
                    updateConfirmed: false,
                    hasBmv: "1",
                    displayTeams: '',
                    displayRooms: "",
                    rooms: [],
                    hasSeries: "",
                    parentSlug: "",
                    hasPublicMemberDashboard: "",
                    initUsers: [],
                    initGuests: [],
                    notifyOption: null,
                    meetingHasStarted: false,
                    globalAiEnabled: "",
                    globalTranscriptsEnabled: "",
                    boardableVideoStarted: false,
                    hasAi: false
                }
            },
            async mounted() {
                this.$set(this.form, 'notify', false);
                this.$set(this.form, 'ms_room_email', '' || '');
                this.$set(this.form, 'ms_room_name', '' || '');
                if (this.displayRooms) {
                    this.fetchRooms();
                }
                if(!this.edit){
                    await this.fetchAssignables()
                    this.$set(this.form, 'dates', [this.dateObj()]);
                    this.$set(this.form, 'remote_option', (this.hasBmv ? 'boardable_video_conference' : 'third_party_remote'));
                    this.$set(this.form, 'meeting_type', 'single');
                    this.$set(this.form, 'minutes_type', 'free_form');
                    this.$set(this.form, 'description', '');
                    this.$set(this.form, 'repeat_period', 'week');
                    this.$set(this.form, 'weekly_interval', '1');
                    this.$set(this.form, 'monthly_interval', '1');
                    this.$set(this.form, 'monthly_repeat_type', 'numbered-day');
                    this.$set(this.form, 'location', '');
                    this.$set(this.form, 'title', '');
                    this.$set(this.form, 'owner_id', 403839);
                    this.$set(this.form, 'public_member_dashboard', false);
                    this.$set(this.form, 'public_page', false);
                    this.$set(this.form, "timezone",  'America/New_York')
                    this.$set(this.form, 'enable_recording', false);
                    this.$set(this.form, 'enable_transcription', "");
                    this.$set(this.form, 'enable_ai_summary', "");

                } else {
                    this.$set(this.form, 'guestsChanged', [])
                    this.$set(this.form, 'usersChanged', [])
                    this.$set(this.meetingTypes, 'singleMeeting', (this.form.additional_dates.length || this.editType === 'Series' ? false : true));
                    this.$set(this.meetingTypes, 'recurringMeeting', "");
                    this.$set(this.meetingTypes, 'multiDayMeeting', (this.form.additional_dates.length ? true : false));
                    this.$set(this.meetingSections.descriptionAndDetails, 'completedText', this.removeHtmlTags(this.form.description));
                    this.$set(this.meetingSections.videoAndCollaboration, 'completedText', this.form.location);
                    this.$set(this.form, 'calendar_type', true ? 'set' : 'schedule')
                    this.$set(this.form, 'assignable_class', `App\\Boardable\\Meetings\\Meeting`)
                    this.$set(this.form, 'assignable_id', 526572)
                    this.$set(this.form, 'series_choice', "single")
                    this.$set(this.form, "timezone",  'America/New_York')
                    this.$set(this.form, 'notify_changed_invitees', false)
                    this.$set(this.form, 'enable_recording', "");
                    this.$set(this.form, 'enable_transcription', "");
                    this.$set(this.form, 'enable_ai_summary', "");

                    this.scheduler = this.form.alternative_dates ? true : false;
                    this.showVideo = true;
                    this.showInvitees = true;
                    this.showDateAndTime = true;

                    if(this.parentSlug){
                        this.$set(this.form, 'meeting_type', 'single')
                        this.$set(this.form, 'follows', this.parentSlug)
                    }

                    await this.fetchData();
                    this.scrollToContainer();
                }
            },
            computed: {
                titleFilteredList() {
                    return Object.values(this.meetingTitles).filter((item) => {
                        if(this.form.title){
                            return this.form.title.toLowerCase().split(' ').every(v => item.toLowerCase().includes(v));
                        }
                    });
                },
                addDatesLabel() {
                    return this.form.meeting_type !== 'scheduler' ? `Add Day` : `Add Option`;
                }
            },
            watch: {
                'form.remote_option': function (newVal) {
                    if(['boardable_video_conference', 'no_remote'].includes(newVal))
                        this.passcodeRequired = false
                }
            },
            methods: {
                fetchRooms() {
                    axios.get('/microsoft/rooms')
                        .then(response => this.rooms = response.data.rooms || [])
                        .catch(() => this.rooms = []);
                },
                roomLabel(room) {
                    let label = room.name;
                    if (room.capacity) label += ' · seats ' + room.capacity;
                    return label;
                },
                selectRoom(event) {
                    const room = this.rooms.find(r => r.email === event.target.value);
                    const prevName = this.form.ms_room_name;

                    this.$set(this.form, 'ms_room_email', room ? room.email : '');
                    this.$set(this.form, 'ms_room_name', room ? room.name : '');

                    if (room) {
                        this.form.location = room.name;
                    } else if (prevName && this.form.location === prevName) {
                        this.form.location = '';
                    }
                    this.meetingSections.videoAndCollaboration.completedText = this.form.location;
                },
                handleTranscriptionToggle(){
                    if(!this.form.enable_transcription){
                        this.form.enable_ai_summary = false;
                    }
                },
                cancelModal(){
                    $('#cancel-meeting').modal('show');
                },
                boardableVideoText(){
                    if(this.hasBmv){
                        return 'Access video/audio, share your screen, chat, and review documents within Boardable.'
                    } else {
                        return 'Unavailable on current plan. Please contact our <a href="mailto:sales@boardable.com?subject=Boardable Video">sales team</a> to upgrade.'
                    }
                },
                reload(e) {
                    window.location.href = e.target.value;
                },
                scrollToContainer(){
                    const hash = window.location.hash;
                    if (hash) {
                        const element = document.querySelector(hash);
                        if (element) {
                            const container = this.$refs[hash.substring(1)];
                            container.click();
                            element.scrollIntoView({ behavior: 'smooth' });
                        }
                    }
                },
                fetchData() {
                    axios.post(Boardable.data_url('assignables'), {
                        model_type: 'meeting',
                        model_id: "526572"
                    }).then((response) => {
                        this.assignable_groups = response.data.assignable_groups || []
                        this.assignable_users = response.data.assignable_users || []

                        this.form.invitee_ids = response.data.selected_users || []
                        this.form.group_ids = response.data.selected_groups || []

                        this.initUsers = this.form.invitee_ids
                        this.initGuests = []


                        this.$nextTick(() => this.$refs.user_select.initValues())
                        this.loading = false
                    })
                },
                handleSeriesUpdate(e){
                    for(seriesData in e){
                        this.form[seriesData] = e[seriesData]
                    }
                },
                handleScheduler(e){
                    this.scheduler = e;
                    e ? this.form.meeting_type = 'scheduler' : this.form.meeting_type = 'single'

                    if(this.edit) {
                        e ? this.form.calendar_type = 'schedule' : this.form.calendar_type = 'set'
                    }
                },
                removeHtmlTags(htmlString) {
                    const tmp = document.createElement('DIV');
                    tmp.innerHTML = htmlString;
                    return tmp.textContent || tmp.innerText || '';
                },
                headerClass(section){
                    if(this.meetingSections[section].completed){
                        if(section === 'descriptionAndDetails' && !this.form.title){
                            return 'collapsed text-gray-700';
                        } else {
                            return 'collapsed text-success';
                        }
                    } else if (!this.meetingSections[section].opened){
                        return 'collapsed text-gray-700';
                    } else {
                        return 'collapsed';
                    }
                },
                checkStatus(section){
                    for(meetingSection in this.meetingSections){
                        section === meetingSection ? this.meetingSections[meetingSection].opened = !this.meetingSections[meetingSection].opened : this.meetingSections[meetingSection].opened = false;
                    }
                    if(section === 'videoAndCollaboration'){
                        this.showVideo = true;
                    }
                    if(section === 'invitees'){
                        this.showInvitees = true;
                    }

                    if(section === 'dateAndTime'){
                        this.showDateAndTime = true;
                    }
                },
                checkMeetingType(typeOfMeeting){
                    for(meetingType in this.meetingTypes){
                        (typeOfMeeting === meetingType ? this.meetingTypes[meetingType] = true : this.meetingTypes[meetingType] = false);
                    }
                    typeOfMeeting === 'recurringMeeting' ? this.form.meeting_type = 'series' : this.form.meeting_type = 'single'
                    typeOfMeeting !== 'singleMeeting' ? this.scheduler = false : null;

                    // Ensure completed text is updated when switching meeting type
                    if(this.form.meeting_type === 'series') {
                        this.$refs['series-dates'].handleRecurrenceUpdates()
                    } else if (this.form.meeting_type === 'single') {
                        this.$refs['non-series-dates'].handleSingleDayUpdates()
                    }
                },
                nextSection(currentSection, nextSection){
                    if (currentSection === 'dateAndTime' && this.hasTimeErrors()) {
                        return;
                    }
                    this.meetingSections[currentSection].completed = true;
                    const next = this.$refs[nextSection]
                    const current = this.$refs[currentSection]

                    if(!this.parentSlug) {
                        window.history.replaceState(null, '', window.location.pathname + '#' + nextSection);
                    }
                    next.click();

                    if(currentSection === 'videoAndCollaboration'){
                        this.meetingSections.videoAndCollaboration.completedText = this.form.location;
                    }
                },
                hasTimeErrors(){
                    // Only count errors for the meeting type that's actually
                    // visible — stale errors from a previous type would
                    // otherwise lock the submit button with no UI to clear them.
                    const errors = this.form.errors;
                    if (this.form.calendar_type === 'schedule') {
                        for (let i = 0; i < (this.form.schedulerDates || []).length; i++) {
                            if (errors.has(`schedulerDates.${i}.from`) || errors.has(`schedulerDates.${i}.to`)) return true;
                        }
                        return false;
                    }
                    if (this.form.meeting_type === 'series' && this.form.series_choice !== 'subsequent') {
                        return errors.has('series_from') || errors.has('series_to');
                    }
                    for (let i = 0; i < (this.form.dates || []).length; i++) {
                        if (errors.has(`dates.${i}.from`) || errors.has(`dates.${i}.to`)) return true;
                    }
                    return false;
                },
                backSection(currentSection, nextSection){
                    const next = this.$refs[nextSection]
                    next.click();
                },
                updateTitle(title){
                    this.form.title = title;
                    this.showSearchResults = false;
                },
                hideSearchResults(){
                    this.showTitle = true;
                    setTimeout( () => this.showSearchResults = false, 200);
                },
                fetchAssignables() {
                    axios.post(Boardable.data_url('assignables'), assignableParams).then( response => {
                        this.assignable_groups = response.data.assignable_groups
                        this.assignable_users = response.data.assignable_users
                        this.form.group_ids = response.data.selected_groups
                        this.form.invitee_ids  = response.data.selected_users
                        if(!this.form.group_ids.length) {
                            response.data.selected_users.push(403839);
                        }

                        if(!this.form.invitee_ids.length && !this.edit)
                            this.form.invitee_ids.push(403839)

                        this.$nextTick( () => {
                            this.$refs.user_select.reset()
                            this.loading = false
                        })
                    })
                },
                updateThirdParty($event) {
                    this.$set(this.form, 'remote_url', $event?.remote_url)
                    this.$set(this.form, 'remote_url_description', $event?.remote_url_description)
                },
                updateRsvpOptions($event) {
                    this.$set(this.form, 'disable_remote_rsvp', $event)
                },
                confirmSubmit(notifyOption = ''){
                    this.updateConfirmed = true;
                    this.form.notify_changed_invitees = (notifyOption === 'new');
                    this.submitForm();
                },
                submitForm() {
                    // Non-reactive flag — immune to Vue tick timing, set synchronously
                    if (this._isSubmitting) return;

                    if (this.hasTimeErrors()) {
                        alert('Please fix the meeting time errors before saving.');
                        return;
                    }

                    this._isSubmitting = true;

                    if(this.edit && !this.parentSlug) {
                        const initialGuestEmails = this.initGuests.map(guest => guest.email);
                        const currentGuestEmails = this.form.guests.map(guest => guest.email);

                        const initialUserIds = this.initUsers;
                        const currentUserIds = this.form.invitee_ids;

                        this.form.guestsChanged =
                            currentGuestEmails.some(email => !initialGuestEmails.includes(email)) ||
                            initialGuestEmails.some(email => !currentGuestEmails.includes(email));

                        this.form.usersChanged =
                            currentUserIds.some(id => !initialUserIds.includes(id)) ||
                            initialUserIds.some(id => !currentUserIds.includes(id));
                    }

                    // If the third party remote option is selected, set it to the selected type (zoom_integration, etc.)
                    if (this.form.meeting_type === 'scheduler' && !this.edit) this.form.schedulerDates = this.form.dates;

                    if (this.form.published && this.form.notify === true) {
                        if (!this.updateConfirmed) {
                            // Release the lock so the modal's Confirm button can re-enter
                            this._isSubmitting = false;
                            if((this.form.guestsChanged || this.form.usersChanged) && this.form.series_choice !== 'subsequent'){
                                $('#update-series-new-invitees').modal('show');
                            } else {
                                $('#update-series').modal('show');
                            }
                            return false;
                        }
                        this.formSubmittingNotify = true;
                    } else {
                        this.formSubmitting = true;
                    }

                    this.form.post(this.$refs.form.action)
                        .then(response => {
                            window.location = response.data.url;
                            this.formSubmitting = false;
                        })
                        .catch((e) => {
                            this._isSubmitting = false;
                            this.formSubmitting = false;
                            this.formSubmittingNotify = false;

                            if (e.response?.status === 409
                                && e.response.data?.code === 'microsoft_reauthorization_required') {
                                this.promptMicrosoftReauthorization(e.response.data);
                                return;
                            }

                            // Open the date and time section if not opened
                            if (!this.meetingSections.dateAndTime.opened) {
                                this.$refs['dateAndTime'].click();
                            }

                            // Check for error response and status code
                            if (e.response) {
                                if (e.response.status === 512) {
                                    Alert.alert({
                                            title: 'Could not create meeting',
                                            text: e.response.data.message || "An unknown error occurred, if this persists please contact Customer Service."
                                    });
                                } else if (e.response.status === 500) {
                                    $toast.error(e.response.data.message || "An unknown error occurred, if this persists please contact Customer Service.");
                                } else {
                                    $toast.error(e.response.data.message || "An error occurred while submitting the form.");
                                }
                            } else {
                                $toast.error("An error occurred while submitting the form.");
                            }
                            if (window.heap) {
                                heap.track('Error while creating meeting');
                            }
                        });
                },
                promptMicrosoftReauthorization(recovery) {
                    Alert.confirm({
                        title: 'Reconnect Microsoft',
                        message: recovery.message,
                        btn_label: 'Reconnect and create meeting',
                        btn_class: 'btn-primary',
                    }, () => {
                        const authUrl = new URL(recovery.reauthorize_url, window.location.origin);
                        authUrl.searchParams.set('attempt', Date.now().toString());
                        const authWindow = window.open(
                            authUrl.toString(),
                            'microsoftMeetingAuth',
                            'width=900,height=700,toolbar=no,menubar=no,scrollbars=yes,resizable=yes'
                        );

                        if (!authWindow) {
                            $toast.error('Please allow popups to reconnect Microsoft. Your meeting is still saved.');
                            return;
                        }

                        let closeTimer = null;
                        const cleanup = () => {
                            window.removeEventListener('message', messageHandler);
                            if (closeTimer) clearInterval(closeTimer);
                        };
                        const messageHandler = (event) => {
                            if (event.origin !== window.location.origin) {
                                return;
                            }

                            if (event.data?.type === 'microsoft-auth-error') {
                                cleanup();
                                this.resumeMicrosoftMeeting(recovery);
                                return;
                            }

                            if (event.data?.type !== 'onedrive-picker-token' || !event.data?.access_token) {
                                return;
                            }

                            cleanup();
                            this.resumeMicrosoftMeeting(recovery);
                        };

                        window.addEventListener('message', messageHandler);
                        closeTimer = setInterval(() => {
                            if (authWindow.closed) cleanup();
                        }, 500);
                    });
                },
                resumeMicrosoftMeeting(recovery) {
                    this._isSubmitting = true;
                    this.formSubmitting = true;

                    axios.post(recovery.resume_url, {resume_key: recovery.resume_key})
                        .then(response => {
                            window.location = response.data.url;
                        })
                        .catch((e) => {
                            this._isSubmitting = false;
                            this.formSubmitting = false;

                            if (e.response?.status === 409
                                && e.response.data?.code === 'microsoft_reauthorization_required') {
                                this.promptMicrosoftReauthorization(e.response.data);
                                return;
                            }

                            $toast.error(e.response?.data?.message || 'The meeting could not be resumed. Please try again.');
                        });
                },
            }
        });
    