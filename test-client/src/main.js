(() => {
    "use strict";

    // =========================================================
    // GLOBAL ERROR HANDLER
    // =========================================================

    window.addEventListener("error", (event) => {
        console.error("[GLOBAL JS ERROR]", event.error || event.message);

        const status = document.getElementById("status");

        if (status) {
            status.textContent =
                "Frontend error: " +
                (event.error?.message || event.message);
        }
    });

    window.addEventListener("unhandledrejection", (event) => {
        console.error(
            "[UNHANDLED PROMISE]",
            event.reason
        );

        const status = document.getElementById("status");

        if (status) {
            status.textContent =
                "Frontend promise error: " +
                (event.reason?.message || event.reason);
        }
    });


    // =========================================================
    // WAIT UNTIL DOM IS READY
    // =========================================================

    function startApp() {

        console.log(
            "=================================================="
        );
        console.log(
            "[APP] Final Expense LiveKit frontend starting"
        );
        console.log(
            "=================================================="
        );


        // -----------------------------------------------------
        // Verify LiveKit SDK
        // -----------------------------------------------------

        if (!window.LivekitClient) {

            console.error(
                "[APP] LivekitClient is NOT available."
            );

            setStatus(
                "LiveKit JavaScript SDK failed to load. Check browser console."
            );

            return;
        }

        console.log(
            "[APP] LivekitClient loaded successfully"
        );


        const Livekit = window.LivekitClient;

        const {
            Room,
            RoomEvent,
            Track,
            ConnectionState,
        } = Livekit;


        if (!Room || !RoomEvent || !Track) {

            console.error(
                "[APP] Required LiveKit classes are missing.",
                {
                    Room,
                    RoomEvent,
                    Track,
                }
            );

            setStatus(
                "LiveKit SDK loaded incorrectly. Check browser console."
            );

            return;
        }


        // =====================================================
        // DOM
        // =====================================================

        const connectButton =
            document.getElementById("connectButton");

        const disconnectButton =
            document.getElementById("disconnectButton");

        const statusElement =
            document.getElementById("status");

        const participantsElement =
            document.getElementById("participants");


        if (!connectButton) {

            console.error(
                "[APP] connectButton not found"
            );

            return;
        }

        if (!disconnectButton) {

            console.error(
                "[APP] disconnectButton not found"
            );

            return;
        }

        if (!statusElement) {

            console.error(
                "[APP] status element not found"
            );

            return;
        }


        // =====================================================
        // STATE
        // =====================================================

        let room = null;
        let connecting = false;


        // =====================================================
        // STATUS
        // =====================================================

        function setStatus(message) {

            console.log(
                "[STATUS]",
                message
            );

            statusElement.textContent =
                message;
        }


        // =====================================================
        // PARTICIPANTS
        // =====================================================

        function updateParticipants() {

            if (!participantsElement) {
                return;
            }

            if (!room) {

                participantsElement.textContent = "";

                return;
            }

            const participants = [];

            room.remoteParticipants.forEach(
                (participant) => {

                    participants.push(
                        `${participant.identity} (${participant.kind})`
                    );
                }
            );

            if (participants.length === 0) {

                participantsElement.textContent =
                    "No remote participants yet.";

            } else {

                participantsElement.textContent =
                    "Participants: " +
                    participants.join(", ");
            }
        }


        // =====================================================
        // AGENT DETECTION
        // =====================================================

        function isAgentParticipant(participant) {

            if (!participant) {
                return false;
            }

            const identity =
                String(participant.identity || "").toLowerCase();

            const name =
                String(participant.name || "").toLowerCase();

            return (
                identity.includes("agent") ||
                identity.includes("final-expense") ||
                name.includes("final-expense") ||
                name.includes("sara")
            );
        }


        // =====================================================
        // REMOTE AUDIO
        // =====================================================

        async function attachRemoteAudio(
            track,
            publication,
            participant
        ) {

            try {

                if (
                    track.kind !== Track.Kind.Audio
                ) {
                    return;
                }

                console.log(
                    "[AUDIO] Remote audio subscribed",
                    {
                        participant:
                            participant.identity,
                        source:
                            publication.source,
                    }
                );

                const audio =
                    track.attach();

                audio.autoplay = true;
                audio.playsInline = true;

                audio.dataset.participant =
                    participant.identity;

                audio.style.display = "none";

                document.body.appendChild(
                    audio
                );

                try {

                    await audio.play();

                    console.log(
                        "[AUDIO] Remote audio playback started"
                    );

                } catch (playError) {

                    console.warn(
                        "[AUDIO] play() blocked",
                        playError
                    );
                }

                if (
                    isAgentParticipant(participant)
                ) {

                    setStatus(
                        "Final Expense agent connected. You can speak now."
                    );
                }

            } catch (error) {

                console.error(
                    "[AUDIO] Failed to attach remote audio",
                    error
                );
            }
        }


        // =====================================================
        // REMOVE AUDIO
        // =====================================================

        function removeParticipantAudio(
            identity
        ) {

            document
                .querySelectorAll(
                    "audio[data-participant]"
                )
                .forEach((audio) => {

                    if (
                        audio.dataset.participant ===
                        identity
                    ) {

                        try {
                            audio.pause();
                            audio.srcObject = null;
                        } catch (_) {}

                        audio.remove();
                    }
                });
        }


        // =====================================================
        // GET FRESH TOKEN
        // =====================================================

        async function getFreshToken() {

            console.log(
                "[TOKEN] Requesting /token"
            );

            const response =
                await fetch(
                    `/token?t=${Date.now()}`,
                    {
                        method: "GET",
                        cache: "no-store",
                        headers: {
                            "Cache-Control":
                                "no-cache",
                            "Pragma":
                                "no-cache",
                        },
                    }
                );

            console.log(
                "[TOKEN] HTTP status",
                response.status
            );

            if (!response.ok) {

                throw new Error(
                    `Token endpoint returned HTTP ${response.status}`
                );
            }

            const data =
                await response.json();

            console.log(
                "[TOKEN] Response",
                data
            );

            if (!data.token) {

                throw new Error(
                    "Token response does not contain token"
                );
            }

            if (!data.livekit_url) {

                throw new Error(
                    "Token response does not contain livekit_url"
                );
            }

            if (!data.room) {

                throw new Error(
                    "Token response does not contain room"
                );
            }

            return data;
        }


        // =====================================================
        // CLEANUP
        // =====================================================

        async function cleanupRoom() {

            if (!room) {
                return;
            }

            console.log(
                "[ROOM] Cleaning up"
            );

            try {

                await room.localParticipant
                    .setMicrophoneEnabled(false);

            } catch (error) {

                console.warn(
                    "[ROOM] Mic disable warning",
                    error
                );
            }

            try {

                await room.disconnect();

            } catch (error) {

                console.warn(
                    "[ROOM] Disconnect warning",
                    error
                );
            }

            document
                .querySelectorAll(
                    "audio[data-participant]"
                )
                .forEach((audio) => {

                    try {
                        audio.pause();
                        audio.srcObject = null;
                    } catch (_) {}

                    audio.remove();
                });

            room = null;

            updateParticipants();
        }


        // =====================================================
        // REGISTER ROOM EVENTS
        // =====================================================

        function registerRoomEvents() {

            room.on(
                RoomEvent.ParticipantConnected,
                (participant) => {

                    console.log(
                        "[ROOM] Participant connected",
                        participant.identity,
                        participant.kind
                    );

                    updateParticipants();

                    if (
                        isAgentParticipant(
                            participant
                        )
                    ) {

                        setStatus(
                            "Final Expense agent joined."
                        );
                    }
                }
            );


            room.on(
                RoomEvent.ParticipantDisconnected,
                (participant) => {

                    console.log(
                        "[ROOM] Participant disconnected",
                        participant.identity
                    );

                    removeParticipantAudio(
                        participant.identity
                    );

                    updateParticipants();
                }
            );


            room.on(
                RoomEvent.TrackSubscribed,
                async (
                    track,
                    publication,
                    participant
                ) => {

                    console.log(
                        "[ROOM] TrackSubscribed",
                        {
                            participant:
                                participant.identity,
                            kind:
                                track.kind,
                            source:
                                publication.source,
                        }
                    );

                    await attachRemoteAudio(
                        track,
                        publication,
                        participant
                    );
                }
            );


            room.on(
                RoomEvent.TrackUnsubscribed,
                (
                    track,
                    publication,
                    participant
                ) => {

                    console.log(
                        "[ROOM] TrackUnsubscribed",
                        participant.identity,
                        track.kind
                    );

                    try {
                        track.detach();
                    } catch (_) {}
                }
            );


            room.on(
                RoomEvent.ConnectionStateChanged,
                (state) => {

                    console.log(
                        "[ROOM] Connection state:",
                        state
                    );

                    if (
                        state ===
                        ConnectionState.Connected
                    ) {

                        console.log(
                            "[ROOM] LiveKit connected"
                        );
                    }
                }
            );


            room.on(
                RoomEvent.Disconnected,
                (reason) => {

                    console.log(
                        "[ROOM] Disconnected:",
                        reason
                    );

                    if (!connecting) {

                        setStatus(
                            "Disconnected."
                        );
                    }

                    updateParticipants();
                }
            );


            room.on(
                RoomEvent.MediaDevicesError,
                (error) => {

                    console.error(
                        "[ROOM] MediaDevicesError",
                        error
                    );

                    setStatus(
                        "Microphone error: " +
                        (error?.message || error)
                    );
                }
            );


            room.on(
                RoomEvent.LocalTrackPublished,
                (publication) => {

                    console.log(
                        "[ROOM] Local track published",
                        {
                            source:
                                publication.source,
                            kind:
                                publication.kind,
                        }
                    );
                }
            );


            room.on(
                RoomEvent.LocalTrackUnpublished,
                (publication) => {

                    console.log(
                        "[ROOM] Local track unpublished",
                        publication
                    );
                }
            );
        }


        // =====================================================
        // CONNECT
        // =====================================================

        async function connect() {

            console.log(
                "=================================================="
            );

            console.log(
                "[CONNECT] BUTTON CLICKED"
            );

            console.log(
                "=================================================="
            );


            if (connecting) {

                console.warn(
                    "[CONNECT] Already connecting"
                );

                return;
            }


            connecting = true;

            connectButton.disabled = true;

            setStatus(
                "Requesting a new LiveKit session..."
            );


            try {

                // ------------------------------------------------
                // Clean previous room completely.
                // ------------------------------------------------

                await cleanupRoom();


                // ------------------------------------------------
                // New room + new token + new dispatch.
                // ------------------------------------------------

                const session =
                    await getFreshToken();


                console.log(
                    "[CONNECT] Session",
                    session
                );


                // ------------------------------------------------
                // Create Room.
                // ------------------------------------------------

                room = new Room({
                    adaptiveStream: true,
                    dynacast: true,
                });


                registerRoomEvents();


                // ------------------------------------------------
                // Connect LiveKit.
                // ------------------------------------------------

                setStatus(
                    "Connecting to LiveKit..."
                );


                await room.connect(
                    session.livekit_url,
                    session.token,
                    {
                        autoSubscribe: true,
                    }
                );


                console.log(
                    "[CONNECT] Connected",
                    {
                        room:
                            room.name,
                        state:
                            room.state,
                    }
                );


                // ------------------------------------------------
                // Enable microphone.
                // ------------------------------------------------

                setStatus(
                    "Starting microphone..."
                );


                await room.localParticipant
                    .setMicrophoneEnabled(
                        true,
                        {
                            echoCancellation:
                                true,
                            noiseSuppression:
                                true,
                            autoGainControl:
                                true,
                        }
                    );


                console.log(
                    "[MIC] enabled:",
                    room.localParticipant
                        .isMicrophoneEnabled
                );


                const mic =
                    room.localParticipant
                        .getTrackPublication(
                            Track.Source.Microphone
                        );


                console.log(
                    "[MIC] publication:",
                    mic
                );

                console.log(
                    "[MIC] track:",
                    mic?.track
                );


                // ------------------------------------------------
                // Current remote participants.
                // ------------------------------------------------

                updateParticipants();


                let agentFound = false;


                room.remoteParticipants.forEach(
                    (participant) => {

                        console.log(
                            "[REMOTE]",
                            participant.identity,
                            participant.kind
                        );

                        if (
                            isAgentParticipant(
                                participant
                            )
                        ) {

                            agentFound = true;

                            console.log(
                                "[AGENT] Already present",
                                participant.identity
                            );
                        }
                    }
                );


                if (agentFound) {

                    setStatus(
                        "Final Expense agent connected. You can speak now."
                    );

                } else {

                    setStatus(
                        "Microphone active. Waiting for Final Expense agent..."
                    );
                }

            } catch (error) {

                console.error(
                    "[CONNECT] FAILED",
                    error
                );

                setStatus(
                    "Connection failed: " +
                    (
                        error?.message ||
                        error
                    )
                );

                await cleanupRoom();

                connectButton.disabled = false;

            } finally {

                connecting = false;
            }
        }


        // =====================================================
        // DISCONNECT
        // =====================================================

        async function disconnect() {

            console.log(
                "[DISCONNECT] clicked"
            );

            await cleanupRoom();

            connectButton.disabled = false;

            setStatus(
                "Disconnected. Click Connect to start a new session."
            );
        }


        // =====================================================
        // BUTTON EVENTS
        // =====================================================

        connectButton.addEventListener(
            "click",
            connect
        );

        disconnectButton.addEventListener(
            "click",
            disconnect
        );


        // =====================================================
        // INITIAL
        // =====================================================

        connectButton.disabled = false;
        disconnectButton.disabled = false;

        setStatus(
            "Click Connect to start a new LiveKit session."
        );


        console.log(
            "[APP] Frontend initialized successfully"
        );
    }


    // =========================================================
    // START
    // =========================================================

    if (
        document.readyState === "loading"
    ) {

        document.addEventListener(
            "DOMContentLoaded",
            startApp
        );

    } else {

        startApp();
    }

})();