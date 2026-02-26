import json
import io
from datetime import datetime

import streamlit as st
from playwright.sync_api import sync_playwright
import requests
from lxml.html import fromstring


def timestamp():
    return datetime.now().strftime("%Y%m%d%H%M%S")


def remove_html_tags(text):
    return fromstring(text).text_content() if text else ""


def main():
    st.image("theplant-logo.png")
    st.title("Mastodon posts fetcher")

    url = st.text_input("Enter the Mastodon address from which to fetch posts (e.g. https://ec.social-network.europa.eu/@EUCommission):", "")
    number_of_posts = st.number_input("Enter the number of posts to fetch (default 100):", min_value=1, value=100, step=1)

    if st.button("Fetch posts"):
        if not url:
            st.error("Please enter a Mastodon address.")
            return

        with st.spinner("Fetching posts — this may take a while..."):
            responses = []

            with sync_playwright() as p:
                p.selectors.set_test_id_attribute("id")

                def get_next_posts(request_url, last_post_id):
                    next_url = f"{request_url}&max_id={last_post_id}"
                    resp = requests.get(next_url)
                    if resp.status_code == 200:
                        body = resp.json()
                        if body:
                            last_id = None
                            for r in body:
                                r["content"] = remove_html_tags(r.get("content", ""))
                                last_id = r.get("id")
                                responses.append(r)

                            if last_id and len(responses) < number_of_posts:
                                get_next_posts(request_url, last_id)

                def handle_response(request):
                    try:
                        if "statuses?exclude_replies" in request.url:
                            resp = request.response()
                            if resp and resp.status == 200:
                                body = resp.json()
                                if body:
                                    last_id = None
                                    for r in body:
                                        r["content"] = remove_html_tags(r.get("content", ""))
                                        last_id = r.get("id")
                                        responses.append(r)

                                    if last_id and len(responses) < number_of_posts:
                                        get_next_posts(request.url, last_id)
                    except Exception:
                        pass

                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.on("request", handle_response)

                # Navigate to the provided URL so the page issues the statuses API calls
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=90000)
                    # Give the page a short time to load and for network calls to be issued
                    page.wait_for_timeout(3000)
                except Exception as e:
                    st.warning(f"Navigation error: {e}")

                # Close browser
                page.context.close()
                browser.close()

        # Trim to requested number
        posts = responses[:int(number_of_posts)]
        jsonposts = {"posts": posts}

        # Prepare download
        data = json.dumps(jsonposts, indent=2)
        b = io.BytesIO(data.encode("utf-8"))
        fname = f"{timestamp()}-posts.json"

        st.success(f"Fetched {len(posts)} posts")
        st.download_button(label="Download posts JSON", data=b, file_name=fname, mime="application/json")


if __name__ == "__main__":
    main()
