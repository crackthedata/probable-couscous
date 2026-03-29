// Set your Python tracking server URL here (e.g., your Raspberry Pi public IP or ngrok domain)
const TRACKING_SERVER_URL = "https://your-custom-domain.com";

function processTrackedDrafts() {
    var label = GmailApp.getUserLabelByName("TrackMe");

    // If the label doesn't exist, log an error and exit
    if (!label) {
        console.error("The label 'TrackMe' was not found. Please create it first.");
        return;
    }

    // Optimization: First check if there are any threads with the label AND a draft.
    // If none exist, we can exit early and save API calls.
    var trackedThreads;
    try {
        trackedThreads = GmailApp.search('label:TrackMe is:draft');
    } catch (e) {
        console.error("Error searching for tracked threads: " + e);
        return;
    }

    if (trackedThreads.length === 0) {
        return; // Exits naturally cleanly
    }

    var trackedThreadIds = trackedThreads.map(function(t) { return t.getId(); });

    var drafts;
    try {
        drafts = GmailApp.getDrafts();
    } catch (e) {
        console.error("Error fetching drafts: " + e);
        return;
    }

    for (var i = 0; i < drafts.length; i++) {
        try {
            var draft = drafts[i];
            var message = draft.getMessage();
            var thread = message.getThread();

            // Only process if the draft thread matches our search for labeled threads
            if (trackedThreadIds.indexOf(thread.getId()) !== -1) {
                var body = message.getBody();
                // Generate a unique ID for this email
                var emailId = "id_" + new Date().getTime();

                var encSubj = encodeURIComponent(message.getSubject() || "No Subject");
                var encTo = encodeURIComponent(message.getTo() || "Unknown Recipient");

                var rawFrom = message.getFrom() || "";
                var accountMatch = rawFrom.match(/<([^>]+)>/);
                var account = accountMatch ? accountMatch[1] : rawFrom.trim();
                if (!account) account = "Unknown Account";

                var encAccount = encodeURIComponent(account);

                // 1. Inject Open Tracker (Python Server)
                var pixelUrl = TRACKING_SERVER_URL + '/open/' + emailId + '?subject=' + encSubj + '&recipient=' + encTo + '&account=' + encAccount;
                var pixel = '<img src="' + pixelUrl + '" width="1" height="1" alt="" style="display:none;" />';

                // 2. Wrap Links for Click Tracking
                var trackedBody = body.replace(/href="([^"]*)"/gi, function (match, p1) {
                    // Don't double-wrap or wrap internal protocol links (mailto:)
                    if (p1.includes(TRACKING_SERVER_URL) || p1.startsWith("mailto:")) {
                        return match;
                    }
                    return 'href="' + TRACKING_SERVER_URL + '/click?id=' + emailId + '&subject=' + encSubj + '&recipient=' + encTo + '&account=' + encAccount + '&url=' + encodeURIComponent(p1) + '"';
                });

                // 3. Update the draft and send it
                var updatedDraft = draft.update(message.getTo(), message.getSubject(), "", {
                    htmlBody: trackedBody + pixel,
                    cc: message.getCc(),
                    bcc: message.getBcc()
                });

                // Add a small delay to give Google's backend time to persist the updated draft
                Utilities.sleep(1000);

                updatedDraft.send();
                console.log("Sent tracked email with ID: " + emailId + " to: " + message.getTo());
                
                // Extra safety sleep to prevent rate limiting if sending multiple quickly
                Utilities.sleep(1000);
            }
        } catch (e) {
            console.error("Error processing individual draft at index " + i + ": " + e);
            // Skip this faulty draft but keep processing others
            continue;
        }
    }
}
